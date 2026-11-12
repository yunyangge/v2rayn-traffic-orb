#!/usr/bin/python3
"""Rolling per-workload budget for Xray proxy outbound traffic only."""
import argparse
import collections
import ctypes
import csv
import fcntl
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import signal
import sys
import shutil
import subprocess
import time

APP_ROOT = Path(os.environ.get('TRAFFIC_ORB_HOME', Path.home() / 'Library/Application Support/TrafficOrb'))
ASSETS = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / ('assets' if getattr(sys, 'frozen', False) else 'resources')
ROOT = APP_ROOT / 'data' / 'proxy-guard'
XRAY_CONFIG = Path(os.environ.get('TRAFFIC_ORB_CONFIG', Path.home() / 'Library/Application Support/v2rayN/binConfigs/config.json'))
PROXIES = {'xray', 'v2ray', 'sing-box', 'clash', 'mihomo', 'ss-local', 'sslocal'}
LIBPROC = ctypes.CDLL('/usr/lib/libproc.dylib') if sys.platform == 'darwin' else None
if LIBPROC:
    LIBPROC.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    LIBPROC.proc_pidpath.restype = ctypes.c_int


def executable_path(pid, command):
    # Resolve the actual executable, rather than logging positional arguments
    # (which may be URLs or credentials). proc_pidpath also preserves spaces.
    if LIBPROC:
        buffer = ctypes.create_string_buffer(4096)
        if LIBPROC.proc_pidpath(pid, buffer, len(buffer)) > 0:
            return os.fsdecode(buffer.value)
    try:
        return os.readlink('/proc/' + str(pid) + '/exe')
    except OSError:
        return command.split(' ', 1)[0]


def read_config(path):
    value = json.loads(path.read_text())
    limit = value.get('limit_bytes')
    if not isinstance(limit, (int, float)) or not math.isfinite(limit) or not 1e8 <= limit <= 1e15:
        raise ValueError('Proxy threshold must be 0.1–1,000,000 GB')
    if not isinstance(value.get('enabled'), bool):
        raise ValueError('enabled must be a boolean')
    if value.get('window_seconds') != 3600 or value.get('restart_block_seconds') != 3600:
        raise ValueError('Proxy protection uses a one-hour window and restart block')
    return value


def atomic_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')))
    temp.replace(path)


def processes():
    raw = subprocess.check_output(
        ['/bin/ps', '-axo', 'uid=,pid=,ppid=,lstart=,args='], text=True, timeout=5)
    result = {}
    for line in raw.splitlines():
        fields = line.split(None, 8)
        if len(fields) != 9:
            continue
        uid, pid, ppid = map(int, fields[:3])
        command = fields[8]
        executable = executable_path(pid, command)
        script = re.search(r'(?:^|\s)(/\S+\.(?:py|js|mjs|cjs|sh))(?=\s|$)', command)
        if script:
            label = script.group(1)
        else:
            label = executable
        start = ' '.join(fields[3:8])
        identity = label
        if script is None and ' -c ' in command:
            identity = command  # Keep unrelated inline programs separate; never log their code.
        elif script is None and ' -m ' in command:
            module = re.search(r' -m (\S+)', command)
            identity = label + ' -m ' + module.group(1) if module else label
        result[pid] = {'uid': uid, 'pid': pid, 'ppid': ppid, 'start': start,
                       'key': str(pid) + ':' + start, 'label': label,
                       'signature': hashlib.sha256(identity.encode()).hexdigest(),
                       'proxy': bool(re.search(r'/(?:' + '|'.join(PROXIES) + r')(?:\s|$)', command, re.I))}
    return result


def endpoint(value):
    """nettop: IPv4 host:port; IPv6 host.port."""
    value = value.strip()
    host, _, port = value.rpartition(':') if value.count(':') < 2 else value.rpartition('.')
    try:
        loopback = ipaddress.ip_address(host.split('%')[0]).is_loopback
    except ValueError:
        loopback = host == 'localhost'
    return loopback, int(port) if port.isdigit() else None


class Routes:
    """Xray access events are the authority for proxy versus direct routing."""
    pattern = re.compile(r'from\s+(?:(tcp|udp):)?(?:127\.0\.0\.1|\[::1\]):(\d+)\s+accepted\s+.*?\[([^\]]+?)\s*(?:->|>>)\s*([^\]]+)\]')

    def __init__(self):
        self.entries = {}
        self.path = None
        self.inode = None
        self.offset = 0
        self.ports = set()
        self.error = '等待 Xray 路由记录'
        self.remainder = ''
        self.anchor = b''

    def accept(self, line):
        match = self.pattern.search(line)
        if match:
            protocol, port, inbound, outbound = match.groups()
            if inbound.strip() not in ('api', 'metrics'):
                self.entries[(protocol or ('udp' if 'accepted udp:' in line else 'tcp'), int(port))] = outbound.strip().startswith('proxy')

    def update(self):
        try:
            try:
                config = json.loads(XRAY_CONFIG.read_text())
                path = Path(config.get('log', {}).get('access', ''))
                self.ports = {int(x['port']) for x in config.get('inbounds', [])
                              if x.get('protocol') in ('socks', 'http', 'mixed')}
                self.path = path if path.is_file() else None
            except (OSError, ValueError, KeyError):
                pass  # v2rayN may remove its generated config after starting.
            if not self.path or not self.path.is_file():
                self.error = '未找到 Xray 路由记录；请开启 v2rayN 文件日志'
                return
            stat = self.path.stat()
            if stat.st_ino != self.inode or stat.st_size < self.offset:
                self.offset, self.inode, self.remainder = 0, stat.st_ino, ''
                self.anchor = b''
            with self.path.open('rb') as stream:
                if self.anchor:
                    stream.seek(self.offset - len(self.anchor))
                    if stream.read(len(self.anchor)) != self.anchor:
                        self.offset, self.remainder = 0, ''
                stream.seek(self.offset)
                raw = self.remainder + stream.read().decode('utf-8', errors='replace')
                self.offset = stream.tell()
                stream.seek(max(0, self.offset - 64))
                self.anchor = stream.read()
            lines = raw.split('\n')
            self.remainder = lines.pop()
            for line in lines:
                self.accept(line)
            self.error = ''
        except OSError as error:
            self.error = str(error)


def parse_frame(rows, procs, ports, routes):
    counts = collections.defaultdict(int)
    pid = None
    for row in rows:
        if not row or len(row) < 4:
            continue
        name = row[0]
        if not name.startswith(('tcp4 ', 'tcp6 ', 'udp4 ', 'udp6 ')):
            match = re.search(r'\.(\d+)$', name)
            pid = int(match.group(1)) if match else None
            continue
        if pid not in procs or procs[pid]['proxy']:
            continue
        try:
            count = max(0, int(row[2] or 0)) + max(0, int(row[3] or 0))
        except ValueError:
            continue
        if not count or '<->' not in name:
            continue
        left, right = name.split(' ', 1)[1].split('<->', 1)
        local_loop, local_port = endpoint(left)
        peer_loop, peer_port = endpoint(right)
        if row[1] == 'lo0' or (local_loop and peer_loop):
            # Count only the client side of a local forward proxy.
            protocol = name[:3]
            if (local_loop and peer_loop and (peer_port in ports or protocol == 'udp') and local_port not in ports
                    and routes.entries.get((protocol, local_port)) is True):
                counts[pid] += count
    return counts


class Budget:
    def __init__(self, config, state=None):
        self.config = config
        self.history = {}
        self.blocked = (state or {}).get('blocked', {})
        for key, value in (state or {}).get('history', {}).items():
            value['samples'] = collections.deque(value['samples'])
            self.history[key] = value

    def trim(self, now):
        cutoff = now - self.config['window_seconds']
        for key, item in list(self.history.items()):
            while item['samples'] and item['samples'][0][0] <= cutoff:
                item['samples'].popleft()
            if not item['samples']:
                del self.history[key]
        self.blocked = {k: v for k, v in self.blocked.items() if v['until'] > now}

    def record(self, proc, count, now):
        item = self.history.setdefault(proc['key'], {
            'label': proc['label'], 'signature': proc['signature'], 'samples': collections.deque()})
        if count:
            item['samples'].append([now, count])

    def totals(self):
        totals = collections.defaultdict(int)
        for item in self.history.values():
            totals[item['signature']] += sum(n for _, n in item['samples'])
        return totals

    def export(self):
        return {'blocked': self.blocked, 'history': {
            k: dict(v, samples=list(v['samples'])) for k, v in self.history.items()}}


class Guard:
    def __init__(self, config_path):
        ROOT.mkdir(parents=True, exist_ok=True)
        self.config_path = config_path
        if not config_path.exists():
            shutil.copyfile(ASSETS / 'default-proxy-guard-settings.json', config_path)
        self.config = read_config(config_path)
        try:
            state = json.loads((ROOT / 'state.json').read_text())
        except (OSError, ValueError):
            state = {}
        self.budget = Budget(self.config, state)
        self.stop = False
        self.child = None
        self.pending = {}
        self.events = collections.deque(maxlen=30)
        self.ports = set(self.config['proxy_ports'])
        self.routes = Routes()
        self.log('started', limit_bytes=self.config['limit_bytes'], window_seconds=self.config['window_seconds'])

    def log(self, event, **values):
        record = dict(time=time.time(), event=event, **values)
        self.events.append(record)
        path = ROOT / 'events.jsonl'
        if path.exists() and path.stat().st_size > 4_000_000:
            path.replace(ROOT / 'events.previous.jsonl')
        with path.open('a') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')

    def refresh_ports(self, procs):
        self.ports = self.routes.ports or set(self.config['proxy_ports'])

    def eligible(self, proc):
        return proc['uid'] == os.getuid() and proc['pid'] not in (os.getpid(), os.getppid()) and proc['pid'] > 1 and not proc['proxy']

    def terminate(self, proc, procs, now, reason, total):
        # Revalidate start time immediately before every signal to avoid PID reuse.
        current = processes().get(proc['pid'])
        if not current or current['key'] != proc['key'] or not self.eligible(current):
            return
        targets = {proc['pid']}
        while True:
            new = {p['pid'] for p in procs.values() if p['ppid'] in targets and self.eligible(p)}
            if new.issubset(targets):
                break
            targets |= new
        for pid in sorted(targets, reverse=True):
            p = procs.get(pid)
            if p is None:
                continue
            try:
                os.kill(pid, signal.SIGTERM)
                self.pending[p['key']] = dict(proc=p, after=now + 2)
                self.log('terminated', pid=pid, label=p['label'], reason=reason, rolling_bytes=total)
            except ProcessLookupError:
                pass
            except PermissionError:
                self.log('permission_denied', pid=pid, label=p['label'])
                self.pending[p['key']] = dict(proc=p, after=now + 60, denied=True)

    def enforce(self, procs, now, active):
        totals = self.budget.totals()
        for proc in procs.values():
            if not self.eligible(proc) or proc['key'] in self.pending or proc['pid'] not in active:
                continue
            signature = proc['signature']
            count = totals.get(signature, 0)
            blocked = self.budget.blocked.get(signature)
            if count >= self.config['limit_bytes'] and not blocked:
                blocked = {'until': now + self.config['restart_block_seconds'], 'label': proc['label']}
                self.budget.blocked[signature] = blocked
                atomic_json(ROOT / 'state.json', self.budget.export())
            if blocked:
                self.terminate(proc, procs, now, 'rolling_budget' if count >= self.config['limit_bytes'] else 'restart_block', count)
        for key, pending in list(self.pending.items()):
            if now < pending['after']:
                continue
            proc = procs.get(pending['proc']['pid'])
            if proc and proc['key'] == key and not pending.get('denied'):
                try:
                    os.kill(proc['pid'], signal.SIGKILL)
                    self.log('force_killed', pid=proc['pid'], label=proc['label'])
                except ProcessLookupError:
                    pass
            self.pending.pop(key, None)

    def status(self, now, procs):
        totals = self.budget.totals()
        active = {}
        for proc in procs.values():
            count = totals.get(proc['signature'], 0)
            if count:
                active[proc['signature']] = {'label': proc['label'], 'bytes': count, 'pid': proc['pid']}
        atomic_json(ROOT / 'status.json', dict(updated=now, guard_pid=os.getpid(),
            limit_bytes=self.config['limit_bytes'], window_seconds=self.config['window_seconds'],
            scope='xray_proxy_only', baseline='installation onward; first nettop snapshot discarded',
            enabled=self.config.get('enabled', True), route_error=self.routes.error,
            route_entries=len(self.routes.entries),
            proxy_ports=sorted(self.ports), top=sorted(active.values(), key=lambda x: x['bytes'], reverse=True)[:20],
            blocked=self.budget.blocked, recent_events=list(self.events)))

    def run(self):
        lock = (ROOT / 'guard.lock').open('a')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.close()
            return
        (ROOT / 'guard.pid').write_text(str(os.getpid()))
        try:
            self.monitor()
        finally:
            (ROOT / 'guard.pid').unlink(missing_ok=True)
            lock.close()

    def monitor(self):
        def stop(*_):
            self.stop = True
            if self.child:
                self.child.terminate()
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        while not self.stop:
            self.child = subprocess.Popen(['/usr/bin/nettop', '-d', '-L', '0', '-s', '1', '-n', '-x',
                '-J', 'interface,bytes_in,bytes_out'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, bufsize=1)
            frame, first, last_save, last_ports = [], True, 0, 0
            try:
                for row in csv.reader(self.child.stdout):
                    if self.stop:
                        break
                    if row and row[0] == '' and 'bytes_in' in row:
                        if frame:
                            now = time.time()
                            self.config = read_config(self.config_path)
                            self.budget.config = self.config
                            procs = processes()
                            self.routes.update()
                            if now - last_ports >= 15:
                                self.refresh_ports(procs)
                                last_ports = now
                            self.budget.trim(now)
                            counts = {}
                            if not first and not self.routes.error and any(p['proxy'] for p in procs.values()):
                                counts = parse_frame(frame, procs, self.ports, self.routes)
                                for pid, count in counts.items():
                                    if self.eligible(procs[pid]):
                                        self.budget.record(procs[pid], count, now)
                            first = False
                            if self.config.get('enabled', True):
                                self.enforce(procs, now, set(counts))
                            if now - last_save >= 5:
                                self.status(now, procs)
                                atomic_json(ROOT / 'state.json', self.budget.export())
                                last_save = now
                            frame = []
                        continue
                    frame.append(row)
            except Exception as error:
                self.log('sampler_error', error=str(error))
            finally:
                self.child.terminate()
                try:
                    self.child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.child.kill()
                self.child.stdout.close()
                atomic_json(ROOT / 'state.json', self.budget.export())
            if not self.stop:
                self.log('sampler_restart')
                time.sleep(2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=APP_ROOT / 'proxy-guard-settings.json')
    args = parser.parse_args()
    Guard(args.config).run()
