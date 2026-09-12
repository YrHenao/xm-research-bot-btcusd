"""Use the same Python detectors; MT4 EA alone validates and sends demo orders."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import time
from .__main__ import load_config
from .market import read_bars
from .mt4_import import import_config
from .signals import decide


def command(cfg,meta,bars):
    import_config(cfg,meta,bars,0.)  # Verify pairing and demo contract, no silent partial file.
    if cfg['strategy']['timeout_enabled']: raise ValueError('Puente demo no implementa timeout; desactivelo')
    if cfg['news']['required'] or cfg['news']['path']: raise ValueError('Esta prueba requiere noticias desactivadas')
    if cfg['strategy']['reward_risk']!=2: raise ValueError('El EA de esta prueba usa target 2:1')
    if len(bars)<cfg['strategy']['warmup']: raise ValueError('Historial insuficiente')
    close=bars[-1].time+60
    if not 0<=meta['server_time']-close<=cfg['risk']['max_age_seconds']: raise ValueError('Datos antiguos/mercado cerrado')
    side,explanation=decide(bars,cfg['strategy'])
    if not side: return None,explanation
    distance=max(sum(b.high-b.low for b in bars[-14:])/14*cfg['strategy']['stop_atr'],
                 meta['min_stop'],cfg['symbols']['bitcoin']['contract']['min_stop'])
    if not math.isfinite(distance) or distance<=0: raise ValueError('Distancia invalida')
    return [1,meta['account_login'],meta['server'],meta['symbol'],close,side,distance,2,
            int(cfg['strategy']['stop_loss_enabled'])],explanation


def main():
    p=argparse.ArgumentParser(); p.add_argument('--folder',required=True,help='Terminal Common/Files/BTCResearch')
    p.add_argument('--config',default='config.mt4.json'); a=p.parse_args()
    cfg=load_config(a.config)
    if not cfg.get('data_policy',{}).get('contract_verified'): raise ValueError('Importar contrato y hacer backtest primero')
    folder=Path(a.folder); seen=None
    print('Solo demo. El EA necesita EnableDemoOrders=true para enviar. Ctrl+C detiene el puente.',flush=True)
    try:
        while not (folder/'STOP').exists():
            try:
                path=folder/'live.json'
                age=time.time()-path.stat().st_mtime
                if not 0<=age<=90: raise ValueError('Snapshot antiguo')
                meta=json.loads(path.read_text(encoding='utf-8-sig'))
                key=(meta['account_login'],meta['server'],meta['last_time'])
                if key!=seen:
                    bars=read_bars(folder/'live.csv')
                    row,explanation=command(cfg,meta,bars)
                    if row:
                        temp=folder/'command.csv.tmp'
                        with temp.open('w',newline='',encoding='ascii') as f:
                            csv.writer(f).writerow(row); f.flush(); os.fsync(f.fileno())
                        temp.replace(folder/'command.csv')
                    seen=key
                    print(json.dumps({'signal':row,'explanation':explanation}),flush=True)
            except (OSError,ValueError,KeyError) as exc:
                print(f'Esperando exportacion coherente: {exc}',flush=True)
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        # Expire any signal not yet consumed. Existing positions remain open.
        (folder/'STOP').touch()


if __name__=='__main__': main()
