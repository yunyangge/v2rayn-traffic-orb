import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('guard', Path(__file__).resolve().parents[1] / 'src/proxy_guard.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
CONFIG = {'enabled': True, 'limit_bytes': 5_000_000_000, 'window_seconds': 3600,
          'restart_block_seconds': 3600, 'proxy_ports': [10808]}


class ProxyGuardTests(unittest.TestCase):
    def test_default_opt_in_and_invalid_threshold(self):
        old_root = guard.ROOT
        with tempfile.TemporaryDirectory() as tmp:
            guard.ROOT = Path(tmp) / 'data'
            path = Path(tmp) / 'settings.json'
            try:
                monitor = guard.Guard(path)
                self.assertFalse(monitor.config['enabled'])
                for value in [0, -1, float('nan'), float('inf')]:
                    path.write_text(json.dumps(dict(CONFIG, limit_bytes=value)))
                    with self.assertRaises(ValueError): guard.read_config(path)
            finally:
                guard.ROOT = old_root

    def test_route_log_rotation_and_removed_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, log = Path(tmp) / 'xray.json', Path(tmp) / 'access.txt'
            config.write_text(json.dumps({'log': {'access': str(log)}, 'inbounds': [{'protocol': 'socks', 'port': 10808}]}))
            log.write_text('from 127.0.0.1:50001 accepted //example.test:443 [socks >> proxy]\n')
            with patch.object(guard, 'XRAY_CONFIG', config):
                routes = guard.Routes(); routes.update()
                self.assertTrue(routes.entries[('tcp', 50001)])
                config.unlink()
                log.write_text('from 127.0.0.1:50002 accepted //direct.test:443 [socks -> direct]\n')
                routes.update()
                self.assertFalse(routes.entries[('tcp', 50002)])
                self.assertFalse(routes.error)
                config.write_text(json.dumps({'log': {}}))
                routes.update()
                self.assertTrue(routes.error, 'Explicitly disabling access logs must not reuse old routing evidence')

    def test_inline_workloads_have_distinct_identities(self):
        sample = ('501 100 1 Thu Nov 12 13:00:00 2026 /usr/bin/python3 -c first\n'
                  '501 101 1 Thu Nov 12 13:00:00 2026 /usr/bin/python3 -c second\n'
                  '501 102 1 Thu Nov 12 13:00:00 2026 /opt/xray run -c xray.json\n')
        with patch.object(guard.subprocess, 'check_output', return_value=sample):
            procs = guard.processes()
        self.assertNotEqual(procs[100]['signature'], procs[101]['signature'])
        self.assertTrue(procs[102]['proxy'])

    def test_positional_arguments_are_not_logged(self):
        sample = '501 100 1 Thu Nov 12 13:00:00 2026 /usr/bin/curl https://example.test/private-token\n'
        with patch.object(guard.subprocess, 'check_output', return_value=sample), \
             patch.object(guard, 'executable_path', return_value='/usr/bin/curl'):
            proc = guard.processes()[100]
        self.assertEqual(proc['label'], '/usr/bin/curl')
        self.assertNotIn('private-token', json.dumps(proc))

    def test_routing_and_accounting(self):
        routes = guard.Routes()
        routes.accept('2026/11/12 13:13:37 from tcp:127.0.0.1:50001 accepted tcp:example.com:443 [socks >> proxy]')
        routes.accept('2026/11/12 13:13:37 from 127.0.0.1:50002 accepted //example.cn:443 [socks -> direct]')
        routes.accept('2026/11/12 13:13:37 from 127.0.0.1:50003 accepted tcp:127.0.0.1:55839 [api -> api]')
        routes.accept('2026/11/12 13:13:37 from udp:127.0.0.1:50004 accepted udp:example.com:80 [socks -> proxy]')
        self.assertTrue(routes.entries[('tcp', 50001)])
        self.assertFalse(routes.entries[('tcp', 50002)])
        self.assertNotIn(('tcp', 50003), routes.entries)
        procs = {10: {'proxy': False}, 20: {'proxy': True}}
        rows = [
            ['python.10', '', '0', '0'],
            ['tcp4 127.0.0.1:50001<->127.0.0.1:10808', 'lo0', '100', '200'],
            ['tcp4 127.0.0.1:50002<->127.0.0.1:10808', 'lo0', '9000', '9000'],
            ['tcp4 127.0.0.1:50003<->127.0.0.1:18763', 'lo0', '9000', '9000'],
            ['tcp4 127.0.0.1:50005<->127.0.0.1:10808', 'lo0', '9000', '9000'],
            ['tcp4 192.168.1.2:50100<->1.1.1.1:443', 'en0', '9000', '9000'],
            ['udp4 127.0.0.1:50004<->127.0.0.1:10808', 'lo0', '60', '40'],
            ['xray.20', '', '0', '0'],
            ['tcp4 127.0.0.1:10808<->127.0.0.1:50001', 'lo0', '200', '100']]
        self.assertEqual(dict(guard.parse_frame(rows, procs, {10808}, routes)), {10: 400})

    def test_rolling_window_persistence_and_multiple_instances(self):
        budget = guard.Budget(CONFIG)
        proc = {'key': '10:a', 'signature': 'task', 'label': 'a.py'}
        budget.record(proc, 3_000_000_000, 100)
        budget.record(dict(proc, key='11:b'), 2_000_000_000, 200)
        restored = guard.Budget(CONFIG, json.loads(json.dumps(budget.export())))
        self.assertEqual(restored.totals()['task'], CONFIG['limit_bytes'])
        restored.trim(3700)
        self.assertEqual(restored.totals()['task'], 2_000_000_000)
        restored.trim(3800)
        self.assertFalse(restored.totals())

    def test_termination_and_restart_only_on_proxy_usage(self):
        old_root = guard.ROOT
        with tempfile.TemporaryDirectory() as tmp:
            guard.ROOT = Path(tmp)
            path = Path(tmp) / 'config.json'
            path.write_text(json.dumps(CONFIG))
            monitor = guard.Guard(path)
            children = []
            try:
                child = subprocess.Popen(['/bin/sleep', '60']); children.append(child)
                p = guard.processes()[child.pid]
                monitor.budget.record(p, CONFIG['limit_bytes'] - 1, time.time())
                monitor.enforce({child.pid: p}, time.time(), {child.pid})
                self.assertIsNone(child.poll())
                monitor.budget.record(p, 1, time.time())
                monitor.enforce({child.pid: p}, time.time(), {child.pid})
                self.assertEqual(child.wait(timeout=3), -15)
                child2 = subprocess.Popen(['/bin/sleep', '60']); children.append(child2)
                p2 = guard.processes()[child2.pid]
                monitor.enforce({child2.pid: p2}, time.time(), set())
                self.assertIsNone(child2.poll(), 'Direct-only restart must be allowed')
                monitor.enforce({child2.pid: p2}, time.time(), {child2.pid})
                self.assertEqual(child2.wait(timeout=3), -15)
            finally:
                for child in children:
                    if child.poll() is None: child.kill()
                    child.wait()
                guard.ROOT = old_root



if __name__ == '__main__':
    unittest.main(verbosity=2)
