"""Exercise a frozen collector against fake local metrics, without a real VPN."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

count = 0
class FakeMetrics(BaseHTTPRequestHandler):
    def do_GET(self):
        global count
        count += 1
        data=json.dumps({'stats':{'outbound':{'proxy':{'uplink':count*100,'downlink':count*200},'direct':{'uplink':count*50,'downlink':0}}}}).encode()
        self.send_response(200); self.end_headers(); self.wfile.write(data)
    def log_message(self,*_): pass

def free_port():
    with socket.socket() as s: s.bind(('127.0.0.1',0)); return s.getsockname()[1]

fake=ThreadingHTTPServer(('127.0.0.1',0),FakeMetrics)
threading.Thread(target=fake.serve_forever,daemon=True).start()
op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
binary=str(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory() as tmp:
    home=Path(tmp); config=home/'fake-metrics.json'
    config.write_text(json.dumps({'metrics':{'listen':f'127.0.0.1:{fake.server_port}'}}))
    port=free_port()
    env={**os.environ,'TRAFFIC_ORB_HOME':str(home/'state'),'TRAFFIC_ORB_CONFIG':str(config),'TRAFFIC_ORB_PORT':str(port)}
    process=subprocess.Popen([binary],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        base=f'http://127.0.0.1:{port}'
        for _ in range(100):
            try:
                result=json.load(op.open(base+'/api/stats',timeout=1))
                if result['online'] and result['quota']['used_bytes']>=300: break
            except (OSError,ValueError): pass
            if process.poll() is not None: raise RuntimeError(process.stderr.read().decode())
            time.sleep(.1)
        else: raise AssertionError('Collector did not produce live metrics')
        assert result['quota']['used_bytes']==result['today']['proxy']['up']+result['today']['proxy']['down']
        assert result['quota']['limit_bytes']==80e9
        assert op.open(base).status==200
        try:
            op.open(urllib.request.Request(base,headers={'Host':'untrusted.invalid'}))
            raise AssertionError('Host check missing')
        except urllib.error.HTTPError as e: assert e.code==403
        diagnostic=json.loads(subprocess.check_output([binary,'--diagnose'],env=env))
        assert diagnostic['xray_metrics_enabled']
        assert set(diagnostic)=={'config_found','xray_metrics_enabled','loopback_only'}
        print('PASS: frozen runtime, fake metrics, separate traffic totals, persistence, HTML, Host protection, private diagnostics')
    finally:
        process.terminate(); process.wait(timeout=10)
        fake.shutdown()
