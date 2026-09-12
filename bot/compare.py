"""Replay every supplied bar under the three agreed exit configurations."""
import argparse
import copy
import json
from pathlib import Path
from collections import Counter
from .__main__ import load_config
from .market import read_bars
from .backtest import run
from .news import FileNews


def exposure(result,cfg):
    cash=cfg['initial_equity']; peak=cash; worst_float=0.; worst_dd=0.; minimum=cash
    events={}; margin=0.; max_margin=0.; min_free=cash
    per_lot=cfg['symbols']['bitcoin']['contract']['margin_per_lot']
    for t in result['trades']:
        events.setdefault(t['time'],[]).append(('open',t))
        events.setdefault(t['exit_time'],[]).append(('close',t))
    times=sorted(events); index=0
    for point in result['equity']:
        while index<len(times) and times[index]<=point['time']:
            stamp=times[index]
            # Opens at this candle close belong to the next candle.
            deferred=[]
            for kind,t in events[stamp]:
                if kind=='open' and stamp==point['time']: deferred.append((kind,t)); continue
                if kind=='open': margin+=t['lots']*per_lot; max_margin=max(max_margin,margin)
                else: cash+=t['pnl']; margin-=t['lots']*per_lot
            if deferred: events[stamp]=deferred; break
            index+=1
        eq=point['equity']; worst_float=min(worst_float,eq-cash); minimum=min(minimum,eq)
        peak=max(peak,eq); worst_dd=max(worst_dd,peak-eq); min_free=min(min_free,eq-margin)
    return {'worst_floating_pnl_close_m1':worst_float,'min_equity':minimum,
        'max_drawdown_usd':worst_dd,'max_margin_snapshot_model':max_margin,
        'minimum_free_margin_snapshot_model':min_free,
        'max_hold_hours':max(((t['exit_time']-t['time'])/3600 for t in result['trades']),default=0),
        'exits':dict(Counter(t['reason'] for t in result['trades']))}


def main():
    p=argparse.ArgumentParser(); p.add_argument('--data',required=True)
    p.add_argument('--config',default='config.mt4.json'); p.add_argument('--out-dir',default='reports')
    a=p.parse_args(); cfg=load_config(a.config)
    if not cfg.get('data_policy',{}).get('contract_verified'): raise ValueError('Importar primero especificaciones MT4')
    bars=read_bars(a.data)
    if len(bars)<=cfg['strategy']['warmup']: raise ValueError('Historial insuficiente')
    out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
    summary={'bars':len(bars),'first_time':bars[0].time,'last_time':bars[-1].time,
        'time_basis':cfg['data_policy']['time_basis'],'gaps':sum(b.time-bars[i-1].time!=60 for i,b in enumerate(bars) if i),
        'assumptions':cfg['data_policy'],'results':{}}
    for label,stop,timeout in [('stop_timeout',True,True),('no_stop',False,True),('no_stop_no_timeout',False,False)]:
        local=copy.deepcopy(cfg); local['strategy'].update(stop_loss_enabled=stop,timeout_enabled=timeout)
        print(f'Ejecutando {label}: {len(bars)} velas...',flush=True)
        result=run({'bitcoin':bars},local,FileNews(**local['news']))
        result['metadata']={'config':local,'source':a.data,'bars':len(bars)}
        summary['results'][label]={**result['metrics'],**exposure(result,local)}
        (out/f'{label}.json').write_text(json.dumps(result,allow_nan=False),encoding='utf-8')
    (out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
