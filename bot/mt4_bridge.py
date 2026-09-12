"""Use the same Python detectors; MT4 EA alone validates and sends demo orders."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import time
from .__main__ import load_config
from .market import read_bars, aggregate
from .mt4_import import import_config
from .signals import decide


def command(cfg,meta,bars):
    import_config(cfg,meta,bars,0.)  # Verify pairing and demo contract, no silent partial file.
    if cfg['strategy']['timeout_enabled']: raise ValueError('Puente demo no implementa timeout; desactivelo')
    if cfg['news']['required'] or cfg['news']['path']: raise ValueError('Esta prueba requiere noticias desactivadas')
    if cfg['strategy']['reward_risk']!=3: raise ValueError('El EA de esta version usa target 3:1')
    if len(bars)<cfg['strategy']['warmup']: raise ValueError('Historial insuficiente')
    close=bars[-1].time+60
    age=meta['server_time']-close
    if not 0<=age<=cfg['risk']['max_age_seconds']:
        raise ValueError(f'Vela fuera de vigencia: diferencia servidor-cierre={age}s; limite={cfg["risk"]["max_age_seconds"]}s. No determina si el mercado esta cerrado.')
    side,explanation=decide(bars,cfg['strategy'])
    if not side: return None,explanation
    distance=max(sum(b.high-b.low for b in bars[-14:])/14*cfg['strategy']['stop_atr'],
                 meta['min_stop'],cfg['symbols']['bitcoin']['contract']['min_stop'])
    if not math.isfinite(distance) or distance<=0: raise ValueError('Distancia invalida')
    return [2,meta['account_login'],meta['server'],meta['symbol'],close,side,distance,3,
            int(cfg['strategy']['stop_loss_enabled']),cfg['risk']['risk_per_trade']],explanation


def diagnostic(cfg,meta,bars,row,explanation):
    needed=cfg['strategy']['trend_period']+1
    counts={str(m):len(aggregate(bars,m)) for m in cfg['strategy']['trend_frames']}
    missing=[m for m,n in counts.items() if n<needed]
    score=explanation.get('score',0)
    reason=('historial_insuficiente' if missing else 'senal_valida' if row else
            'sin_senal_detectores' if abs(score)<cfg['strategy']['min_votes'] else 'filtros_no_confirman')
    return {'estado':reason,'velas_m1':len(bars),'velas_completas':counts,
            'necesarias_por_filtro':needed,'marcos_insuficientes':missing,
            'segundos_desde_cierre':meta['server_time']-bars[-1].time-60,
            'score':score,'filtros':explanation.get('filters',{}),
            'senal':row,'nota':'Senal no equivale a orden ejecutada'}


def main():
    p=argparse.ArgumentParser(); p.add_argument('--folder',required=True,help='Terminal Common/Files/BTCResearch')
    p.add_argument('--config',default='config.mt4.json'); a=p.parse_args()
    cfg=load_config(a.config)
    if not cfg.get('data_policy',{}).get('contract_verified'): raise ValueError('Importar contrato y hacer backtest primero')
    folder=Path(a.folder); seen=None; last_warning=0
    print('Solo demo. El EA necesita EnableDemoOrders=true para enviar. Ctrl+C detiene el puente.',flush=True)
    try:
        while not (folder/'STOP').exists():
            try:
                path=folder/'live.json'
                age=time.time()-path.stat().st_mtime
                if not 0<=age<=90: raise ValueError(f'Archivo sin actualizar: edad={age:.0f}s; limite=90s. Revisar EA/conexion, no implica cierre del mercado.')
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
                    print(json.dumps(diagnostic(cfg,meta,bars,row,explanation),ensure_ascii=False),flush=True)
            except (OSError,ValueError,KeyError) as exc:
                if time.monotonic()-last_warning>=60:
                    print(f'Esperando exportacion coherente: {exc}',flush=True)
                    last_warning=time.monotonic()
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        # Expire any signal not yet consumed. Existing positions remain open.
        (folder/'STOP').touch()


if __name__=='__main__': main()
