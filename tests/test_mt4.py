import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from bot.market import Bar
from bot.mt4_import import import_config
from bot.mt4_bridge import command, diagnostic, native_frames
from bot.compare import exposure

ROOT=Path(__file__).resolve().parents[1]

class MT4Tests(unittest.TestCase):
    def fixture(self):
        cfg=json.loads((ROOT/'config.example.json').read_text())
        bars=[Bar(1735689600+i*60,100,102,98,100,2) for i in range(65)]
        meta={'schema':1,'mode':'demo','symbol':'BTCUSD','server':'fixture','account_login':123,
            'account_currency':'USD','time_basis':'broker_server','bars':65,
            'first_time':bars[0].time,'last_time':bars[-1].time,'server_time':bars[-1].time+60,
            'spread_source':'current_snapshot_assumption','spread':2,'contract_size':1,
            'quote_to_account':1,'volume_min':.01,'volume_max':10,'volume_step':.01,
            'min_stop':1,'margin_per_lot':1000}
        meta['filter_source']='mt4_native_closed'
        meta['native_frames']={str(m):[[meta['server_time']//(m*60)*(m*60)-(21-i)*m*60,100+i] for i in range(21)] for m in (15,60,240)}
        return cfg,bars,meta

    def test_contract_import_uses_export_not_template(self):
        cfg,bars,meta=self.fixture(); imported=import_config(cfg,meta,bars,7)
        self.assertEqual(imported['symbols']['bitcoin']['contract']['margin_per_lot'],1000)
        self.assertEqual(imported['symbols']['bitcoin']['contract']['commission_roundtrip'],7)
        self.assertFalse(cfg['data_policy']['contract_verified'])
        self.assertTrue(imported['data_policy']['contract_verified'])

    def test_real_or_other_symbol_rejected(self):
        cfg,bars,meta=self.fixture()
        for changes in ({'mode':'real'},{'symbol':'XAUUSD'},{'account_currency':'EUR'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError): import_config(cfg,{**meta,**changes},bars,0)

    def test_mismatched_export_and_invalid_contract_rejected(self):
        cfg,bars,meta=self.fixture()
        for changes in ({'bars':64},{'last_time':0},{'spread':3},{'margin_per_lot':0}):
            with self.subTest(changes=changes),self.assertRaises(ValueError): import_config(cfg,{**meta,**changes},bars,0)

    def test_demo_signal_both_directions_no_stop(self):
        cfg,bars,meta=self.fixture()
        for side in (-1,1):
            with patch('bot.mt4_bridge.decide',return_value=(side,{})):
                row,_=command(cfg,meta,bars)
                self.assertEqual(row[1:4],[123,'fixture','BTCUSD'])
                self.assertEqual(row[0],3); self.assertEqual(row[5],side)
                self.assertEqual(row[7],3); self.assertEqual(row[8],0)
                self.assertEqual(row[9],.00375)

    def test_stale_signal_and_timeout_rejected(self):
        cfg,bars,meta=self.fixture()
        with self.assertRaises(ValueError): command(cfg,{**meta,'server_time':meta['server_time']+120},bars)
        cfg['strategy']['timeout_enabled']=True
        with self.assertRaises(ValueError): command(cfg,meta,bars)

    def test_deployment_sizing_and_target(self):
        from bot.backtest import run
        from bot.news import FileNews
        cfg,bars,_=self.fixture()
        cfg['symbols']['bitcoin']['slippage']=0
        cfg['symbols']['bitcoin']['contract'].update(min_stop=0,margin_per_lot=1,volume_step=.01)
        cfg['risk']['kill_file']=str(ROOT/'tests'/'NO_STOP')
        cfg['risk']['risk_per_trade']=.00375
        def once(history,strategy,enabled): return (1 if len(history)==60 else 0),{}
        current=run({'bitcoin':bars},cfg,FileNews(None,required=False),signal_fn=once)['trades'][0]
        self.assertAlmostEqual(current['lots'],4.68)  # floor((10000*.00375/8)/.01)*.01
        self.assertAlmostEqual(current['target']-current['entry'],24)
        cfg['risk']['risk_per_trade']=.0025; cfg['strategy']['reward_risk']=2
        previous=run({'bitcoin':bars},cfg,FileNews(None,required=False),signal_fn=once)['trades'][0]
        self.assertAlmostEqual(previous['lots'],3.12)
        self.assertAlmostEqual(current['lots']/previous['lots'],1.5)

    def test_diagnostic_distinguishes_history_and_signal(self):
        cfg,bars,meta=self.fixture()
        incomplete=copy.deepcopy(meta); incomplete['native_frames']['240']=[]
        with self.assertRaisesRegex(ValueError,'insuficiente'):
            diagnostic(cfg,incomplete,bars,None,{'score':1,'filters':{}})
        cfg['strategy']['trend_frames']=[]
        self.assertEqual(diagnostic(cfg,meta,bars,None,{'score':0})['estado'],'sin_senal_detectores')
        self.assertEqual(diagnostic(cfg,meta,bars,None,{'score':1})['estado'],'filtros_no_confirman')

    def test_stale_bar_not_accepted_with_fresh_snapshot(self):
        cfg,bars,meta=self.fixture()
        meta['server_time']=bars[-1].time+60+91
        with self.assertRaisesRegex(ValueError,'diferencia servidor-cierre=91s'):
            command(cfg,meta,bars)

    def test_native_frames_reject_future_stale_and_legacy(self):
        cfg,bars,meta=self.fixture()
        old=copy.deepcopy(meta); del old['filter_source']
        with self.assertRaisesRegex(ValueError,'Actualizar'): command(cfg,old,bars)
        future=copy.deepcopy(meta); future['native_frames']['15'][-1][0]+=900
        with self.assertRaisesRegex(ValueError,'abierta/futura'): native_frames(cfg,future)
        stale=copy.deepcopy(meta)
        for row in stale['native_frames']['60']: row[0]-=86400
        with self.assertRaisesRegex(ValueError,'atrasado'): native_frames(cfg,stale)

    def test_native_filters_work_with_gaps_in_m1(self):
        from bot.signals import decide,NAMES
        cfg,bars,meta=self.fixture()
        for direction in (-1,1):
            local=copy.deepcopy(meta)
            for rows in local['native_frames'].values():
                for i,row in enumerate(rows): row[1]=100+direction*i
            signals={name:{'side':direction if i==0 else 0} for i,name in enumerate(NAMES)}
            with patch('bot.signals.analyze',return_value=signals):
                side,explanation=decide(bars[::2],cfg['strategy'],higher_frames=native_frames(cfg,local))
            self.assertEqual(side,direction)
            self.assertEqual(set(explanation['filters'].values()),{direction})

    def test_exposure_counts_floating_and_realized_separately(self):
        cfg,_,_=self.fixture(); cfg['symbols']['bitcoin']['contract']['margin_per_lot']=1000
        result={'trades':[{'time':0,'exit_time':120,'lots':.1,'pnl':10,'reason':'target'},
                          {'time':120,'exit_time':240,'lots':.2,'pnl':-20,'reason':'end'}],
                'equity':[{'time':60,'equity':9900},{'time':120,'equity':10010},
                          {'time':180,'equity':9810},{'time':240,'equity':9990}]}
        stats=exposure(result,cfg)
        self.assertEqual(stats['worst_floating_pnl_close_m1'],-200)
        self.assertEqual(stats['max_margin_snapshot_model'],200)
        self.assertEqual(stats['max_drawdown_usd'],200)
