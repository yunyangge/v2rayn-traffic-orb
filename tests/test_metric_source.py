import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from metric_source import MetricsSource


class FakeStats(BaseHTTPRequestHandler):
    count = 0
    def do_GET(self):
        type(self).count += 1
        data = json.dumps({'stats': {'outbound': {'proxy': {'uplink': self.count * 100, 'downlink': self.count * 200}}}}).encode()
        self.send_response(200); self.end_headers(); self.wfile.write(data)
    def log_message(self, *_):
        pass


class MetricSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = self.root / 'binConfigs/config.json'
        self.config.parent.mkdir()
        self.exe = self.root / 'bin/xray/xray'
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), FakeStats)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.address = f'127.0.0.1:{self.server.server_port}'
        self.config.write_text(json.dumps({'metrics': {'listen': self.address}}))
        self.discovery_count = 0

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.temp.cleanup()

    def command(self, args):
        if args[0] == '/bin/ps':
            self.discovery_count += 1
            return f'9999 {self.exe} run -c config.json\n'
        if '-p' in args:
            return 'p9999\nn' + self.address + '\nn0.0.0.0:45678\n'
        return 'p9999\n'

    def source(self):
        return MetricsSource(self.config, xray_executable=self.exe, command=self.command)

    def test_deleted_config_uses_cached_endpoint(self):
        source = self.source()
        identity, before = source.read()
        self.config.unlink()
        after_identity, after = source.read()
        self.assertEqual(identity, after_identity)
        self.assertGreater(after['proxy']['up'], before['proxy']['up'])
        self.assertEqual(self.discovery_count, 0)

    def test_startup_without_config_discovers_running_xray(self):
        self.config.unlink()
        identity, values = self.source().read()
        self.assertEqual(identity, self.address + ':9999')
        self.assertGreater(values['proxy']['up'], 0)
        self.assertEqual(self.discovery_count, 1)

    def test_changed_port_recovers_without_config(self):
        source = self.source(); source.cached_address = '127.0.0.1:1'
        self.config.unlink()
        self.assertEqual(source.read()[0], self.address + ':9999')

    def test_other_process_is_not_probed(self):
        self.config.unlink()
        source = MetricsSource(self.config, xray_executable=self.exe, command=lambda args: '9999 /some/other/xray run\n')
        with self.assertRaises(ValueError): source.read()

    def test_remote_or_malformed_addresses_rejected(self):
        for value in ['192.0.2.1:80', '0.0.0.0:80', '127.0.0.1:99999', None, 80]:
            with self.assertRaises(ValueError): MetricsSource._address(value)


if __name__ == '__main__': unittest.main()
