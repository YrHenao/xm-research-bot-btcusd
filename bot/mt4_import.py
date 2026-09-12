"""Validate MT4 export and pin broker contract; never invent historical spreads."""
import argparse
import copy
import json
import math
from pathlib import Path
from .__main__ import load_config
from .market import read_bars
from .risk import Contract


def import_config(template, metadata, bars, commission):
    if metadata.get('schema')!=1 or metadata.get('mode')!='demo':
        raise ValueError('Exportacion MT4 demo requerida')
    if 'BTCUSD' not in metadata.get('symbol','') or metadata.get('account_currency')!='USD':
        raise ValueError('Se requiere BTCUSD de cuenta USD')
    if metadata.get('time_basis')!='broker_server': raise ValueError('Base horaria desconocida')
    if not bars or metadata['bars']!=len(bars) or metadata['first_time']!=bars[0].time or metadata['last_time']!=bars[-1].time:
        raise ValueError('CSV y metadatos no corresponden a la misma exportacion')
    if metadata.get('spread_source')!='current_snapshot_assumption': raise ValueError('Fuente de spread desconocida')
    if any(not math.isclose(b.spread,metadata['spread'],abs_tol=1e-9) for b in bars):
        raise ValueError('Spread incoherente con exportacion')
    if not math.isfinite(commission) or commission<0: raise ValueError('Comision invalida')
    cfg=copy.deepcopy(template); sc=cfg['symbols']['bitcoin']
    sc['broker_symbol']=metadata['symbol']
    contract={k:metadata[k] for k in ('contract_size','quote_to_account','volume_min','volume_max','volume_step','min_stop','margin_per_lot')}
    contract.update(currency='USD',commission_roundtrip=commission)
    Contract(**contract)
    sc['contract']=contract
    cfg['data_policy']={'contract_verified':True,'time_basis':'broker_server',
        'spread_source':metadata['spread_source'],'commission_source':'explicit_user_assumption',
        'commission_roundtrip':commission,'server':metadata['server'],
        'note':'Contrato y margen actuales, spread constante supuesto; no incluye swaps ni stop-out.'}
    return cfg


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--data',required=True); p.add_argument('--metadata',required=True)
    p.add_argument('--commission-roundtrip',type=float,required=True,help='USD por lote ida/vuelta; 0 solo si se acepta ese supuesto')
    p.add_argument('--template',default='config.example.json'); p.add_argument('--out',default='config.mt4.json')
    a=p.parse_args()
    cfg=import_config(load_config(a.template),json.loads(Path(a.metadata).read_text(encoding='utf-8-sig')),read_bars(a.data),a.commission_roundtrip)
    Path(a.out).write_text(json.dumps(cfg,indent=2,allow_nan=False),encoding='utf-8')
    print(f'Configuracion importada: {a.out}. Spread historico NO verificado.')


if __name__=='__main__': main()
