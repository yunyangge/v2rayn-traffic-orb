"""Check the frozen, opt-in guard in isolation; never send real proxy traffic."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

binary = str(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    access = home / 'access.txt'
    access.write_text('from 127.0.0.1:54321 accepted //example.test:443 [socks >> proxy]\n')
    config = home / 'xray.json'
    config.write_text(json.dumps({'log': {'access': str(access)}, 'inbounds': [{'protocol': 'socks', 'port': 10808}]}))
    state = home / 'state'
    env = {**os.environ, 'TRAFFIC_ORB_HOME': str(state), 'TRAFFIC_ORB_CONFIG': str(config)}
    process = subprocess.Popen([binary, '--guard'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        path = state / 'data/proxy-guard/status.json'
        for _ in range(450):
            if path.exists():
                status = json.loads(path.read_text())
                break
            if process.poll() is not None: raise RuntimeError(process.stderr.read().decode())
            time.sleep(.1)
        else: raise AssertionError('Frozen guard did not start')
        assert status['scope'] == 'xray_proxy_only'
        assert not status['enabled'] and status['limit_bytes'] == 5e9
        assert not status['route_error'] and status['route_entries'] == 1
        assert status['proxy_ports'] == [10808]
        pid = (state / 'data/proxy-guard/guard.pid').read_text()
        duplicate = subprocess.run([binary, '--guard'], env=env, capture_output=True, timeout=20)
        assert duplicate.returncode == 0
        assert (state / 'data/proxy-guard/guard.pid').read_text() == pid
        print('PASS: frozen guard, isolated settings, opt-in default, Xray route log, singleton')
    finally:
        process.terminate()
        process.wait(timeout=10)
