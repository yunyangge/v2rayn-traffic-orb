import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('collector', ROOT / 'src/collector.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_root = c.ROOT; c.ROOT = Path(self.tmp.name)
        (c.ROOT / 'settings.json').write_text(json.dumps({'daily_limit_gb':80, 'alert_percentages':[80,95,100]}))

    def tearDown(self):
        c.ROOT = self.old_root; self.tmp.cleanup()

    def daily(self, n): return {'proxy':{'up':n,'down':0}, 'direct':dict(c.ZERO)}

    def test_quota_boundaries(self):
        for used, expected in [(63_999_999_999,0),(64e9,80),(76e9,95),(80e9,100),(85e9,100)]:
            q=c.quota_status('2026-01-01',self.daily(used))
            self.assertEqual(q['stage'],expected)
            self.assertEqual(q['remaining_bytes'],max(0,80e9-used))

    def test_setting_is_live(self):
        (c.ROOT/'settings.json').write_text(json.dumps({'daily_limit_gb':100}))
        self.assertEqual(c.quota_status('day',self.daily(80e9))['stage'],80)

    def test_counter_reset(self):
        self.assertEqual(c.delta({'up':150,'down':220},{'up':100,'down':200},True),{'up':50,'down':20})
        self.assertEqual(c.delta({'up':3,'down':7},{'up':100,'down':200},False),{'up':3,'down':7})

    def test_midnight_split(self):
        start=time.mktime(dt.datetime(2026,1,1,23,59,59).timetuple())
        days={}; c.allocate_usage(days,start,start+2,self.daily(100))
        self.assertEqual(days['2026-01-01']['proxy']['up'],50)
        self.assertEqual(days['2026-01-02']['proxy']['up'],50)

    def test_offline_day_reset_preserves_history(self):
        c.STATE={'days':{'1900-01-01':self.daily(77e9)}}
        c.VIEW={'online':False,'today':self.daily(77e9)}
        s=c.public_snapshot()
        self.assertEqual(s['today']['proxy']['up'],0)
        self.assertEqual(c.STATE['days']['1900-01-01']['proxy']['up'],77e9)


if __name__ == '__main__': unittest.main()
