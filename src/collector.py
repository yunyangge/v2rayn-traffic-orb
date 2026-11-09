#!/usr/bin/env python3
"""Local, read-only Xray metrics collector. No third-party dependencies."""
import argparse
import copy
import datetime as dt
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import shutil
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(os.environ.get('TRAFFIC_ORB_HOME', Path.home() / 'Library/Application Support/TrafficOrb'))
ASSETS = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / ('assets' if getattr(sys, 'frozen', False) else 'resources')
DATA = ROOT / 'data'
CONFIG = Path(os.environ.get('TRAFFIC_ORB_CONFIG', Path.home() / 'Library/Application Support/v2rayN/binConfigs/config.json'))
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
LOCK = threading.Lock()
STOP = threading.Event()
ZERO = {'up': 0, 'down': 0}


def local_day(timestamp=None):
    return dt.datetime.fromtimestamp(timestamp if timestamp is not None else time.time()).date().isoformat()


def quota_status(day, daily):
    settings = json.loads((ROOT / 'settings.json').read_text())
    limit = float(settings.get('daily_limit_gb', 80)) * 1_000_000_000
    if not 100_000_000 <= limit <= 1_000_000_000_000_000:
        raise ValueError('每日限额必须大于零。')
    used = daily['proxy']['up'] + daily['proxy']['down']
    percent = used / limit * 100
    stages = sorted(float(v) for v in settings.get('alert_percentages', [80, 95, 100]))
    stage = max((v for v in stages if percent >= v), default=0)
    return {'day': day, 'limit_bytes': limit, 'used_bytes': used,
            'remaining_bytes': max(0, limit - used), 'percent': percent, 'stage': stage}


def allocate_usage(days, previous_time, now, changes):
    # Split an interval crossing midnight proportionally; never charge it all to the new day.
    start = min(previous_time, now)
    duration = now - start
    pieces = []
    while local_day(start) != local_day(now):
        date = dt.datetime.fromtimestamp(start).date() + dt.timedelta(days=1)
        boundary = time.mktime(dt.datetime.combine(date, dt.time()).timetuple())
        pieces.append((local_day(start), (boundary - start) / duration))
        start = boundary
    pieces.append((local_day(now), (now - start) / duration if duration > 0 else 1))
    remaining = copy.deepcopy(changes)
    for index, (day, fraction) in enumerate(pieces):
        daily = days.setdefault(day, {'proxy': dict(ZERO), 'direct': dict(ZERO)})
        for group in changes:
            for direction, count in changes[group].items():
                part = remaining[group][direction] if index == len(pieces) - 1 else int(count * fraction)
                daily[group][direction] += part
                remaining[group][direction] -= part


def public_snapshot():
    with LOCK:
        snapshot = copy.deepcopy(VIEW)
        day = local_day()
        daily = copy.deepcopy(STATE['days'].get(day, {'proxy': dict(ZERO), 'direct': dict(ZERO)}))
    snapshot['today'] = daily
    snapshot['quota'] = quota_status(day, daily)
    return snapshot


def fresh():
    return {'started': dt.datetime.now().astimezone().isoformat(), 'total': {'proxy': dict(ZERO), 'direct': dict(ZERO)}, 'days': {}, 'previous': None}


def delta(current, previous, same_process):
    # A restarted core starts its counters at zero. Never subtract across runs.
    return {k: max(0, v - previous.get(k, 0)) if same_process and v >= previous.get(k, 0) else v for k, v in current.items()}


def source():
    config = json.loads(CONFIG.read_text())
    metrics = config.get('metrics')
    if not metrics:
        raise ValueError('请在 v2rayN 参数设置中开启流量统计或实时速度。')
    address = metrics.get('listen')
    if not address:
        inbound = next((i for i in config.get('inbounds', []) if i.get('tag') == metrics.get('tag')), None)
        if not inbound:
            raise ValueError('未找到 Xray 本地统计端口。')
        address = f"127.0.0.1:{inbound['port']}"
    host, port = address.rsplit(':', 1)
    if host not in ('127.0.0.1', 'localhost', '[::1]'):
        raise ValueError('只允许读取本机统计接口。')
    pid = subprocess.check_output(['/usr/sbin/lsof', '-nP', f'-iTCP:{int(port)}', '-sTCP:LISTEN', '-Fp'], timeout=2, text=True)
    identity = address + ':' + ','.join(line[1:] for line in pid.splitlines() if line.startswith('p'))
    with HTTP.open('http://' + address + '/debug/vars', timeout=2) as response:
        metrics = json.load(response)
    outbound = metrics.get('stats', {}).get('outbound')
    if not isinstance(outbound, dict):
        raise ValueError('统计接口尚未准备好。')
    counters = {'proxy': dict(ZERO), 'direct': dict(ZERO)}
    for tag, counts in outbound.items():
        group = 'proxy' if tag.startswith('proxy') else 'direct' if tag == 'direct' else None
        if group:
            for field, key in [('up', 'uplink'), ('down', 'downlink')]:
                counters[group][field] += max(0, int(counts.get(key, 0)))
    return identity, counters


def persist(state):
    DATA.mkdir(exist_ok=True)
    temporary = DATA / 'usage.tmp'
    temporary.write_text(json.dumps(state, ensure_ascii=False))
    temporary.replace(DATA / 'usage.json')


def collect():
    global STATE, VIEW
    last_mono = None
    last_ok = None
    history = []
    while not STOP.is_set():
        started = time.monotonic()
        now = time.time()
        day = local_day(now)
        try:
            identity, counters = source()
            previous = STATE.get('previous')
            same = previous is not None and previous['identity'] == identity
            elapsed = now - previous['time'] if previous else 0
            speed = {'proxy': dict(ZERO), 'direct': dict(ZERO)}
            changes = {}
            for group in counters:
                change = delta(counters[group], previous['counters'][group] if previous else ZERO, same) if previous else dict(ZERO)
                changes[group] = change
                for direction in ZERO:
                    STATE['total'][group][direction] += change[direction]
                    if same and last_mono is not None and 0 < elapsed < 5:
                        speed[group][direction] = change[direction] / elapsed
            with LOCK:
                # Only split closely observed intervals. After a long outage the timing is unknown.
                allocation_start = previous['time'] if same and 0 < elapsed <= 5 else now
                allocate_usage(STATE['days'], allocation_start, now, changes)
                daily = copy.deepcopy(STATE['days'][day])
                STATE['previous'] = {'identity': identity, 'counters': counters, 'time': now}
            persist(STATE)
            history.append({'time': now, 'up': speed['proxy']['up'], 'down': speed['proxy']['down']})
            history = history[-60:]
            last_ok = now
            last_mono = started
            with LOCK:
                VIEW = {'online': True, 'message': '正在采集', 'speed': speed, 'total': copy.deepcopy(STATE['total']), 'today': copy.deepcopy(daily), 'started': STATE['started'], 'last_ok': last_ok, 'history': list(history)}
        except Exception as error:
            last_mono = None
            message = str(error) if isinstance(error, ValueError) else '等待 v2rayN 的 Xray 统计接口，请确认客户端正在运行。'
            with LOCK:
                VIEW.update(online=False, message=message, speed={'proxy': dict(ZERO), 'direct': dict(ZERO)}, last_ok=last_ok)
        STOP.wait(max(.05, 1 - (time.monotonic() - started)))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get('Host') not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'):
            self.send_error(403)
            return
        path = self.path.split('?', 1)[0]
        if path == '/api/stats':
            body = json.dumps(public_snapshot(), ensure_ascii=False).encode()
            mime = 'application/json; charset=utf-8'
        elif path in ('/', '/index.html'):
            body = (ASSETS / 'index.html').read_bytes()
            mime = 'text/html; charset=utf-8'
        elif path == '/health':
            body = b'{"service":"v2rayn-local-monitor"}'
            mime = 'application/json'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


def main():
    global STATE, VIEW
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=int(os.environ.get('TRAFFIC_ORB_PORT', '18863')))
    parser.add_argument('--diagnose', action='store_true', help='Print connection status without server names or credentials')
    args = parser.parse_args()
    if args.diagnose:
        try:
            config = json.loads(CONFIG.read_text())
            print(json.dumps({'config_found': True, 'xray_metrics_enabled': bool(config.get('metrics')), 'loopback_only': True}))
        except (OSError, ValueError):
            print(json.dumps({'config_found': False, 'xray_metrics_enabled': False, 'loopback_only': True}))
        return
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not (ROOT / 'settings.json').exists():
        shutil.copyfile(ASSETS / 'default-settings.json', ROOT / 'settings.json')
    DATA.mkdir(exist_ok=True)
    try:
        STATE = json.loads((DATA / 'usage.json').read_text())
    except FileNotFoundError:
        STATE = fresh()
    VIEW = {'online': False, 'message': '正在连接统计接口…', 'speed': {'proxy': dict(ZERO), 'direct': dict(ZERO)}, 'total': copy.deepcopy(STATE['total']), 'today': {'proxy': dict(ZERO), 'direct': dict(ZERO)}, 'started': STATE['started'], 'last_ok': None, 'history': []}
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    (DATA / 'server.pid').write_text(str(os.getpid()))
    def stop(*_):
        STOP.set()
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    worker = threading.Thread(target=collect, daemon=True)
    worker.start()
    print(f'Local: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    finally:
        STOP.set()
        worker.join(timeout=6)
        server.server_close()
        (DATA / 'server.pid').unlink(missing_ok=True)


if __name__ == '__main__':
    main()
