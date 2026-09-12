import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from bot.market import Bar,aggregate,validate
from bot.signals import analyze,pivots,line,decide,NAMES
from bot.news import FileNews
from bot.risk import Contract,size_lots,gate,Journal
from bot.backtest import run,exit_price,evaluate
from bot.__main__ import load_config

ROOT=Path(__file__).resolve().parents[1]
def cfg():
    c=load_config(ROOT/'config.example.json'); c['symbols']['bitcoin']['contract'].update(contract_size=100,min_stop=.5,margin_per_lot=10000,commission_roundtrip=7); c['symbols']['bitcoin']['slippage']=.1; c['strategy']['trend_frames']=[]; c['risk']['kill_file']=str(ROOT/'tests'/'NO_STOP'); return c
def bars(n=150): return [Bar(1735689600+i*60,100,102,98,100+(i%3-1)*.5,.2) for i in range(n)]
def buy(history,cfg,enabled): return 1,{'fixture':True}

class Tests(unittest.TestCase):
    def test_01_validate(self): self.assertEqual(len(validate(bars(2))),2)
    def test_02_duplicate(self):
        with self.assertRaises(ValueError): validate([bars(1)[0]]*2)
    def test_03_nan(self):
        with self.assertRaises(ValueError): validate([Bar(0,1,2,1,float('nan'),0)])
    def test_04_aggregate_incomplete(self): self.assertEqual(aggregate(bars(14),15),[])
    def test_05_aggregate_complete(self): self.assertEqual(len(aggregate(bars(30),15)),2)
    def test_06_pivot_delay(self):
        bs=[Bar(i*60,2,5 if i==3 else 3,1,2,0) for i in range(8)]; self.assertIn((3,5,'H',5),pivots(bs[:6],2))
    def test_07_line(self): self.assertEqual(line([(1,3),(2,5),(3,7)]),(2,1))
    def test_08_detectors(self): self.assertEqual(set(analyze(bars(),cfg()['strategy'])),set(NAMES))
    def test_09_future_blind(self):
        c=cfg()['strategy']; bs=bars(); before=[decide(bs[:i],c) for i in range(60,80)]; bs[80:]=[Bar(b.time,1000,1100,900,1000,10) for b in bs[80:]]; self.assertEqual(before,[decide(bs[:i],c) for i in range(60,80)])
    def test_10_news_missing(self): self.assertFalse(FileNews(None).allowed(100,['USD'])[0])
    def test_11_news_optional(self): self.assertTrue(FileNews(None,required=False).allowed(100,['USD'])[0])
    def test_12_contract(self): self.assertAlmostEqual(Contract('USD',100,1,.01,10,.01,0,1000,7).loss(10,9),107)
    def test_13_sizing(self): self.assertEqual(size_lots(1,337,Contract('USD',100,1,.01,100,.01,0,1000,7),5000),0)
    def test_14_gate(self): self.assertIsNone(gate(now=120,bar_close=120,spread=.2,equity=10000,day_start=10000,positions=0,open_risk=0,cfg={**cfg()['risk'],'max_spread':1}))
    def test_15_kill(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'STOP'; p.touch(); r={**cfg()['risk'],'kill_file':str(p),'max_spread':1}; self.assertEqual(gate(now=120,bar_close=120,spread=.2,equity=10000,day_start=10000,positions=0,open_risk=0,cfg=r),'emergency_stop')
    def test_16_journal(self):
        with tempfile.TemporaryDirectory() as td:
            j=Journal(Path(td)/'s.db'); self.assertTrue(j.reserve('x')); self.assertFalse(j.reserve('x')); j.close()
    def test_17_stop_priority(self): self.assertEqual(exit_price({'side':1,'stop':98,'target':104},Bar(0,100,105,97,100,.2),.1)[1],'stop')
    def test_18_replay(self): self.assertGreater(run({'bitcoin':bars()},cfg(),FileNews(None,required=False),signal_fn=buy)['metrics']['trades'],0)
    def test_19_evaluate(self): self.assertIn('comparisons',evaluate({'bitcoin':bars()},cfg(),FileNews(None,required=False)))
    def test_22_stop_toggle_both_sides(self):
        for side,stop,target in [(1,98,104),(-1,104,98)]:
            p={'side':side,'stop':stop,'target':target}
            crossing=Bar(0,100,105,97,100,.2)
            with self.subTest(side=side):
                self.assertEqual(exit_price(p,crossing,.1)[1],'stop')
                self.assertEqual(exit_price(p,crossing,.1,False),(target,'target'))

    def test_23_disabled_stop_keeps_position_until_exit(self):
        for side in (1,-1):
            for reason in ('target','timeout','end'):
                with self.subTest(side=side,reason=reason):
                    c=cfg(); c['strategy']['stop_loss_enabled']=False
                    c['strategy']['reward_risk']=2  # Legacy exit fixture, independent of deployment defaults.
                    c['strategy']['timeout_enabled']=True
                    c['strategy']['max_hold_minutes']=2 if reason=='timeout' else 60
                    bs=bars(63); t=bs[60].time
                    # Entry near 100, nominal stop distance 8, target distance 16.
                    bs[60]=Bar(t,100,110 if side<0 else 101,90 if side>0 else 99,100,.2)
                    bs[61]=Bar(t+60,100,101,99,100,.2)
                    bs[62]=Bar(t+120,100,120 if reason=='target' and side>0 else 101,80 if reason=='target' and side<0 else 99,100,.2)
                    def once(history,strategy,enabled):
                        return (side if len(history)==60 else 0),{'fixture':True}
                    result=run({'bitcoin':bs},c,FileNews(None,required=False),signal_fn=once)
                    self.assertEqual(len(result['trades']),1)
                    trade=result['trades'][0]
                    self.assertEqual(trade['reason'],reason)
                    self.assertEqual(trade['exit_time'],t+180)
                    c['strategy']['stop_loss_enabled']=True
                    baseline=run({'bitcoin':bs},c,FileNews(None,required=False),signal_fn=once)['trades'][0]
                    self.assertEqual(baseline['reason'],'stop')
                    self.assertEqual(baseline['exit_time'],t+60)
                    for key in ('entry','stop','target','lots','risk'):
                        self.assertEqual(trade[key],baseline[key])

    def test_24_stop_config_validation_and_legacy_default(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'config.json'
            c=cfg(); del c['strategy']['stop_loss_enabled']
            path.write_text(json.dumps(c),encoding='utf-8')
            self.assertIs(load_config(path)['strategy']['stop_loss_enabled'],True)
            for value in ('false',0,1,None,[],{}):
                with self.subTest(value=value):
                    c['strategy']['stop_loss_enabled']=value
                    path.write_text(json.dumps(c),encoding='utf-8')
                    with self.assertRaisesRegex(ValueError,'booleano'): load_config(path)
                    with self.assertRaisesRegex(ValueError,'booleano'): run({'bitcoin':bars()},c,FileNews(None,required=False))

    def test_25_backtest_rejects_non_simulation(self):
        c=cfg(); c['mode']='live'
        with self.assertRaisesRegex(ValueError,'simulation'): run({'bitcoin':bars()},c,FileNews(None,required=False))

    def test_26_disabled_timeout_keeps_position_until_target_or_end(self):
        for side in (1,-1):
            for reason in ('target','end'):
                with self.subTest(side=side,reason=reason):
                    c=cfg(); c['strategy'].update(stop_loss_enabled=False,timeout_enabled=False,max_hold_minutes=1)
                    c['strategy']['reward_risk']=2
                    bs=bars(65); t=bs[60].time
                    if reason=='target':
                        bs[64]=Bar(t+240,100,120 if side>0 else 102,80 if side<0 else 98,100,.2)
                    def once(history,strategy,enabled):
                        return (side if len(history)==60 else 0),{'fixture':True}
                    trade=run({'bitcoin':bs},c,FileNews(None,required=False),signal_fn=once)['trades'][0]
                    self.assertEqual(trade['reason'],reason)
                    self.assertEqual(trade['exit_time'],t+300)
                    for legacy in (False,True):
                        c['strategy']['timeout_enabled']=True
                        if legacy: del c['strategy']['timeout_enabled']
                        baseline=run({'bitcoin':bs},c,FileNews(None,required=False),signal_fn=once)['trades'][0]
                        self.assertEqual(baseline['reason'],'timeout')
                        self.assertEqual(baseline['exit_time'],t+120)

    def test_27_timeout_config_validation_and_default(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'config.json'; c=cfg(); del c['strategy']['timeout_enabled']
            path.write_text(json.dumps(c),encoding='utf-8')
            self.assertIs(load_config(path)['strategy']['timeout_enabled'],True)
            for value in ('false',0,1,None,[],{}):
                with self.subTest(value=value):
                    c['strategy']['timeout_enabled']=value
                    path.write_text(json.dumps(c),encoding='utf-8')
                    with self.assertRaisesRegex(ValueError,'timeout_enabled'): load_config(path)
                    with self.assertRaisesRegex(ValueError,'timeout_enabled'): run({'bitcoin':bars()},c,FileNews(None,required=False))

if __name__=='__main__': unittest.main()
