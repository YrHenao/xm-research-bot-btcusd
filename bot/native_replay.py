"""Replay native MT4 filters point-in-time; never use bars not yet closed."""
import argparse
from bisect import bisect_right
from collections import Counter
import csv
import json
import math
from pathlib import Path
from .__main__ import load_config
from .market import Bar,read_bars
from .mt4_import import import_config
from .mt4_bridge import native_frames
from .signals import decide
from .backtest import run
from .compare import exposure
from .news import FileNews


def load_native(folder,meta):
    manifest=json.loads((folder/'native_manifest.json').read_text(encoding='utf-8-sig'))
    if manifest.get('source')!='mt4_native_closed' or manifest.get('time_basis')!='broker_server':
        raise ValueError('Manifiesto nativo requerido')
    if any(manifest.get(k)!=meta.get(k) for k in ('symbol','server')):
        raise ValueError('Servidor/simbolo nativo y M1 no coinciden')
    result={}
    for m in (15,60,240):
        with (folder/f'btcusd_m{m}.csv').open(encoding='utf-8-sig',newline='') as f:
            rows=[(int(r['time']),float(r['close'])) for r in csv.DictReader(f)]
        if not rows: raise ValueError(f'M{m} vacio')
        for i,(t,c) in enumerate(rows):
            if t%(m*60) or not math.isfinite(c) or c<=0 or (i and t<=rows[i-1][0]):
                raise ValueError(f'Serie M{m} invalida')
        entry=manifest['frames'][str(m)]
        if (len(rows),rows[0][0],rows[-1][0])!=(entry['count'],entry['first'],entry['last']):
            raise ValueError(f'M{m} no coincide con manifiesto')
        result[m]=rows
    return result


class NativeSignal:
    def __init__(self,frames,max_age=90):
        self.frames=frames; self.times={m:[t for t,_ in rows] for m,rows in frames.items()}
        self.max_age=max_age; self.blocked=Counter()

    def select(self,now,strategy):
        raw={}; n=strategy['trend_period']+1
        for m in strategy['trend_frames']:
            end=bisect_right(self.times[m],now-m*60)
            raw[str(m)]=self.frames[m][max(0,end-n):end]
        return native_frames({'strategy':strategy,'risk':{'max_age_seconds':self.max_age}},
                             {'filter_source':'mt4_native_closed','server_time':now,'native_frames':raw})

    def __call__(self,history,strategy,enabled):
        now=history[-1].time+60
        try: selected=self.select(now,strategy)
        except ValueError as exc:
            reason='insufficient_native_history' if 'insuficiente' in str(exc) else 'stale_native_history'
            self.blocked[reason]+=1
            return 0,{'native_block':reason}
        return decide(history,strategy,enabled,higher_frames=selected)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--folder',default='data'); p.add_argument('--config',default='config.demo.json')
    p.add_argument('--out',default='reports/native-replay.json')
    a=p.parse_args(); folder=Path(a.folder); cfg=load_config(a.config)
    meta=json.loads((folder/'btcusd_m1.json').read_text(encoding='utf-8-sig'))
    bars=read_bars(folder/'btcusd_m1.csv')
    cfg=import_config(cfg,meta,bars,cfg['symbols']['bitcoin']['contract']['commission_roundtrip'])
    frames=load_native(folder,meta); signal=NativeSignal(frames,cfg['risk']['max_age_seconds'])
    print(f'Replay nativo: {len(bars)} velas M1; lotaje nominal {cfg["risk"]["risk_per_trade"]}, target {cfg["strategy"]["reward_risk"]}:1',flush=True)
    result=run({'bitcoin':bars},cfg,FileNews(**cfg['news']),signal_fn=signal)
    result['exposure']=exposure(result,cfg)
    result['native_blocked']=dict(signal.blocked)
    result['metadata']={'config':cfg,'source':'mt4_native_closed','bars':len(bars),
        'first':bars[0].time,'last':bars[-1].time,'native_counts':{m:len(v) for m,v in frames.items()},
        'note':'Filtro nativo alineado al cierre M1. Spread constante supuesto, comision configurada, sin swaps/stop-out.'}
    out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,allow_nan=False),encoding='utf-8')
    print(json.dumps({'metrics':result['metrics'],'exposure':result['exposure'],'native_blocked':result['native_blocked']},indent=2))
    print(f'Guardado: {out}')


if __name__=='__main__': main()
