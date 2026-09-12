import argparse
import csv
from dataclasses import asdict
import json
import math
from pathlib import Path
import random
from .market import Bar, read_bars
from .news import FileNews
from .backtest import evaluate, run
from .signals import NAMES


def load_config(path):
    with open(path,encoding='utf-8') as f: c=json.load(f)
    def finite(value):
        if isinstance(value,dict): return all(finite(v) for v in value.values())
        if isinstance(value,list): return all(finite(v) for v in value)
        return math.isfinite(value) if isinstance(value,(int,float)) else True
    if not finite(c): raise ValueError('ConfiguraciÃ³n no finita')
    if c['mode']!='simulation': raise ValueError('CLI solo permite simulation')
    r=c['risk']; s=c['strategy']
    s.setdefault('stop_loss_enabled',True)
    if not isinstance(s['stop_loss_enabled'],bool): raise ValueError('stop_loss_enabled debe ser booleano')
    s.setdefault('timeout_enabled',True)
    if not isinstance(s['timeout_enabled'],bool): raise ValueError('timeout_enabled debe ser booleano')
    if not 0<r['risk_per_trade']<=r['max_open_risk']<=0.1 or not 0<r['daily_loss']<1 or r['max_positions']<1: raise ValueError('LÃ­mites de riesgo invÃ¡lidos')
    if not 0<c['train_fraction']<1 or c['initial_equity']<=0 or not 1<=s['pivot_wing'] or s['lookback']<s['warmup'] or s['warmup']<15: raise ValueError('ConfiguraciÃ³n invÃ¡lida')
    if not set(s['enabled'])<=set(NAMES) or s['min_votes']<1 or s['trend_period']<2 or s['stop_atr']<=0 or s['reward_risk']<=0: raise ValueError('Estrategia invÃ¡lida')
    if len(set(s['enabled']))!=len(s['enabled']) or any(not isinstance(n,int) or n<1 for n in s['trend_frames']): raise ValueError('Detectores duplicados o marcos invÃ¡lidos')
    if s['tolerance_atr']<=0 or s['shoulder_tolerance_atr']<=0 or s['max_hold_minutes']<1 or s['level_contacts']<1 or not all(0<r<1 for r in s['fib_ratios']): raise ValueError('Umbrales de patrones invÃ¡lidos')
    if r['max_age_seconds']<0 or c['history_bars']<s['lookback'] or c['news']['before']<0 or c['news']['after']<0: raise ValueError('Ventanas invÃ¡lidas')
    for symbol in c['symbols'].values():
        if symbol['slippage']<0 or symbol['max_spread']<0 or not symbol['news_currencies']: raise ValueError('Costes o cobertura de sÃ­mbolo invÃ¡lidos')
    return c


def main():
    p=argparse.ArgumentParser(description='Bot de investigaciÃ³n MT5; no envÃ­a Ã³rdenes')
    p.add_argument('command',choices=['synthetic','replay','evaluate'])
    p.add_argument('--config',default='config.example.json')
    p.add_argument('--data',action='append',default=[],help='alias=ruta.csv (repetible)')
    p.add_argument('--out',default='report.json')
    p.add_argument('--bars',type=int,default=1200)
    a=p.parse_args()
    if a.command=='synthetic':
        if a.bars<1: p.error('--bars debe ser positivo')
        rng=random.Random(71); price=2000.; bars=[]
        for i in range(a.bars):
            close=max(1,price+math.sin(i/30)*0.3+rng.gauss(0,0.5)); bars.append(Bar(1735689600+i*60,price,max(price,close)+rng.random(),min(price,close)-rng.random(),close,0.2)); price=close
        with open(a.out,'w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(asdict(bars[0]))); w.writeheader(); w.writerows(asdict(b) for b in bars)
        print('Datos SINTÃ‰TICOS creados. No representan precios, noticias ni rentabilidad de XM.'); return
    cfg=load_config(a.config); streams={}
    if not cfg.get('data_policy',{}).get('contract_verified'): raise ValueError('Importe primero el contrato MT4 con bot.mt4_import')
    for item in a.data:
        alias,path=item.split('=',1)
        if alias not in cfg['symbols']: raise ValueError('Alias no configurado')
        streams[alias]=read_bars(path)
    if not streams: p.error('Indique --data alias=archivo.csv')
    news=FileNews(**cfg['news']); result=evaluate(streams,cfg,news) if a.command=='evaluate' else run(streams,cfg,news)
    result['metadata']={'config':cfg,'sources':a.data,'note':'Datos aportados; procedencia no verificada. Los archivos sintÃ©ticos solo prueban software.'}
    Path(a.out).write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8'); print(f'Informe guardado: {a.out}')


if __name__=='__main__': main()
