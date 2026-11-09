"""Locate local Xray metrics without depending on a transient config file."""
import json
from pathlib import Path
import subprocess
import urllib.request


class MetricsSource:
    def __init__(self, config, xray_executable=None, command=None, opener=None):
        self.config = Path(config)
        self.xray_executable = Path(xray_executable) if xray_executable else self.config.parent.parent / 'bin/xray/xray'
        self.command = command or self._command
        self.opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.cached_address = None

    @staticmethod
    def _command(args):
        return subprocess.check_output(args, text=True, timeout=2, stderr=subprocess.DEVNULL)

    @staticmethod
    def _address(value):
        if not isinstance(value, str):
            raise ValueError('无效的 Xray 统计地址。')
        host, _, port = value.rpartition(':')
        if host not in ('127.0.0.1', 'localhost', '[::1]') or not port.isdigit() or not 0 < int(port) < 65536:
            raise ValueError('只允许读取本机 Xray 统计接口。')
        return ('127.0.0.1' if host == 'localhost' else host) + ':' + str(int(port))

    def _configured_address(self):
        config = json.loads(self.config.read_text())
        metrics = config.get('metrics')
        if not isinstance(metrics, dict):
            return None
        if metrics.get('listen'):
            return self._address(metrics['listen'])
        for inbound in config.get('inbounds', []):
            if inbound.get('tag') == metrics.get('tag'):
                host = inbound.get('listen', '127.0.0.1')
                return self._address(f"{host}:{inbound['port']}")
        return None

    def _running_addresses(self):
        """Inspect only v2rayN's Xray process, never arbitrary local services."""
        rows = self.command(['/bin/ps', '-axo', 'pid=,command=']).splitlines()
        executable = str(self.xray_executable)
        for row in rows:
            fields = row.strip().split(None, 1)
            if len(fields) != 2 or not fields[0].isdigit():
                continue
            if fields[1] != executable and not fields[1].startswith(executable + ' '):
                continue
            listeners = self.command(['/usr/sbin/lsof', '-nP', '-a', '-p', fields[0], '-iTCP', '-sTCP:LISTEN', '-Fn'])
            for line in listeners.splitlines():
                if line.startswith('n'):
                    try:
                        yield self._address(line[1:])
                    except ValueError:
                        continue

    def _read(self, address):
        with self.opener.open('http://' + address + '/debug/vars', timeout=1.5) as response:
            metrics = json.load(response)
        if not isinstance(metrics, dict):
            raise ValueError('无效的统计响应。')
        stats = metrics.get('stats')
        outbound = stats.get('outbound') if isinstance(stats, dict) else None
        if not isinstance(outbound, dict):
            raise ValueError('统计接口尚未准备好。')
        # Include the current listener owner so counter resets retain their identity semantics.
        port = address.rsplit(':', 1)[1]
        owners = self.command(['/usr/sbin/lsof', '-nP', '-iTCP:' + port, '-sTCP:LISTEN', '-Fp'])
        pids = [line[1:] for line in owners.splitlines() if line.startswith('p') and line[1:].isdigit()]
        if not pids:
            raise ValueError('Xray 统计接口已停止。')
        counters = {'proxy': {'up': 0, 'down': 0}, 'direct': {'up': 0, 'down': 0}}
        for tag, values in outbound.items():
            group = 'proxy' if tag.startswith('proxy') else 'direct' if tag == 'direct' else None
            if group and isinstance(values, dict):
                for key, source in [('up', 'uplink'), ('down', 'downlink')]:
                    counters[group][key] += max(0, int(values.get(source, 0)))
        self.cached_address = address
        return address + ':' + ','.join(pids), counters

    def read(self):
        candidates = []
        try:
            configured = self._configured_address()
            if configured:
                candidates.append(configured)
        except (OSError, ValueError, KeyError, TypeError):
            # v2rayN can remove or replace generated configuration while Xray is still running.
            pass
        if self.cached_address and self.cached_address not in candidates:
            candidates.append(self.cached_address)
        tried = set()
        for address in candidates:
            tried.add(address)
            try:
                return self._read(address)
            except (OSError, ValueError, TypeError, subprocess.SubprocessError):
                pass
        try:
            for address in self._running_addresses():
                if address in tried:
                    continue
                tried.add(address)
                try:
                    return self._read(address)
                except (OSError, ValueError, TypeError, subprocess.SubprocessError):
                    pass
        except (OSError, subprocess.SubprocessError):
            pass
        raise ValueError('未连接到 v2rayN 的 Xray 统计接口；请确认 Xray 正在运行且流量统计已开启。')
