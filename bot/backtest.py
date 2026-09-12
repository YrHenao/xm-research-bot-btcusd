from collections import Counter
from .signals import decide, NAMES
from .risk import Contract, gate, size_lots
from .market import validate


def exit_price(position,bar,slippage,stop_loss_enabled=True):
    side,stop,target=position['side'],position['stop'],position['target']; add=bar.spread if side<0 else 0; op,hi,lo=bar.open+add,bar.high+add,bar.low+add
    if side>0:
        if stop_loss_enabled and lo<=stop: return min(op,stop)-slippage,'stop'
        if hi>=target: return target,'target'
    else:
        if stop_loss_enabled and hi>=stop: return max(op,stop)+slippage,'stop'
        if lo<=target: return target,'target'
    return None


def run(streams,cfg,news,start=None,end=None,enabled=None,signal_fn=decide):
    if cfg['mode']!='simulation': raise ValueError('Backtest solo permite simulation')
    stop_loss_enabled=cfg['strategy'].get('stop_loss_enabled',True)
    if not isinstance(stop_loss_enabled,bool): raise ValueError('stop_loss_enabled debe ser booleano')
    timeout_enabled=cfg['strategy'].get('timeout_enabled',True)
    if not isinstance(timeout_enabled,bool): raise ValueError('timeout_enabled debe ser booleano')
    for bars in streams.values(): validate(bars)
    contracts={s:Contract(**cfg['symbols'][s]['contract']) for s in streams}
    if any(c.currency!=cfg['account_currency'] for c in contracts.values()): raise ValueError('Moneda de contrato distinta de moneda de cuenta')
    indexed={s:{b.time:(i,b) for i,b in enumerate(bs)} for s,bs in streams.items()}; times=sorted({b.time for bs in streams.values() for b in bs if (start is None or b.time>=start) and (end is None or b.time<end)})
    cash=cfg['initial_equity']; peak=cash; max_dd=0; day=None; day_start=cash; positions={}; trades=[]; curve=[]; blocks=Counter(); explanations=[]; quotes={}
    for now in times:
        current={s:ix[now] for s,ix in indexed.items() if now in ix}
        for s,(_,b) in current.items(): quotes[s]=b.open+b.spread if s in positions and positions[s]['side']<0 else b.open
        def equity(): return cash+sum((quotes[s]-p['entry'])*p['side']*p['lots']*contracts[s].contract_size*contracts[s].quote_to_account-p['lots']*contracts[s].commission_roundtrip for s,p in positions.items())
        if now//86400!=day: day=now//86400; day_start=equity()
        for s,(i,b) in sorted(current.items()):
            bars=streams[s]; sc=cfg['symbols'][s]; contract=contracts[s]
            if s in positions or i<cfg['strategy']['warmup']: continue
            if b.time-bars[i-1].time!=60: blocks['data_gap']+=1; continue
            if any(symbol not in current for symbol in positions): blocks['portfolio_quote_missing']+=1; continue
            history=bars[max(0,i-cfg['history_bars']):i]; side,explanation=signal_fn(history,cfg['strategy'],enabled)
            if not side: continue
            allowed,reason=news.allowed(now,sc['news_currencies']); rc={**cfg['risk'],'max_spread':sc['max_spread']}; blocked=gate(now=now,bar_close=bars[i-1].time+60,spread=b.spread,equity=equity(),day_start=day_start,positions=len(positions),open_risk=sum(p['risk'] for p in positions.values()),cfg=rc)
            if not allowed or blocked: blocks[reason if not allowed else blocked]+=1; continue
            atr=sum(x.high-x.low for x in history[-14:])/14; distance=max(atr*cfg['strategy']['stop_atr'],contract.min_stop); entry=b.open+(b.spread if side>0 else 0)+side*sc['slippage']; stop=entry-side*distance; target=entry+side*distance*cfg['strategy']['reward_risk']; loss=contract.loss(entry,stop)+sc['slippage']*contract.contract_size*contract.quote_to_account
            used_margin=sum(p['lots']*contracts[k].margin_per_lot for k,p in positions.items()); lots=size_lots(equity()*rc['risk_per_trade'],loss,contract,max(0,equity()-used_margin))
            if lots==0 or stop<=0 or target<=0: blocks['size_or_stop_invalid']+=1; continue
            positions[s]={'side':side,'entry':entry,'stop':stop,'target':target,'lots':lots,'risk':loss*lots,'time':now}; explanations.append({'symbol':s,'time':now,'side':side,**explanation})
        for s,(i,b) in current.items():
            if s in positions:
                p=positions[s]; outcome=exit_price(p,b,cfg['symbols'][s]['slippage'],stop_loss_enabled)
                if outcome is None and timeout_enabled and now-p['time']>=cfg['strategy']['max_hold_minutes']*60: outcome=(b.close+(b.spread if p['side']<0 else 0)-p['side']*cfg['symbols'][s]['slippage'],'timeout')
                if outcome:
                    price,reason=outcome; c=contracts[s]; pnl=(price-p['entry'])*p['side']*p['lots']*c.contract_size*c.quote_to_account-p['lots']*c.commission_roundtrip; cash+=pnl; trades.append({**p,'symbol':s,'exit_time':now+60,'exit':price,'pnl':pnl,'reason':reason}); del positions[s]
            quotes[s]=b.close+(b.spread if s in positions and positions[s]['side']<0 else 0)
        eq=equity(); peak=max(peak,eq); max_dd=max(max_dd,(peak-eq)/peak); curve.append({'time':now+60,'equity':eq})
    for s,p in positions.items():
        c=contracts[s]; price=quotes[s]-p['side']*cfg['symbols'][s]['slippage']; pnl=(price-p['entry'])*p['side']*p['lots']*c.contract_size*c.quote_to_account-p['lots']*c.commission_roundtrip; cash+=pnl; trades.append({**p,'symbol':s,'exit_time':times[-1]+60,'exit':price,'pnl':pnl,'reason':'end'})
    if curve: curve[-1]['equity']=cash; peak=max(peak,cash); max_dd=max(max_dd,(peak-cash)/peak)
    wins=sum(t['pnl'] for t in trades if t['pnl']>0); losses=-sum(t['pnl'] for t in trades if t['pnl']<0)
    return {'metrics':{'trades':len(trades),'net_pnl':cash-cfg['initial_equity'],'final_equity':cash,'max_drawdown':max_dd,'expectancy':sum(t['pnl'] for t in trades)/len(trades) if trades else None,'win_rate':sum(t['pnl']>0 for t in trades)/len(trades) if trades else None,'profit_factor':wins/losses if losses else None},'blocked':dict(blocks),'trades':trades,'equity':curve,'explanations':explanations}


def evaluate(streams,cfg,news):
    times=sorted({b.time for bars in streams.values() for b in bars})
    if len(times)<cfg['strategy']['warmup']+20: raise ValueError('Historial insuficiente')
    cut=times[int(len(times)*cfg['train_fraction'])]; variants={'all':None,**{f'only_{n}':[n] for n in NAMES},**{f'without_{n}':[x for x in cfg['strategy']['enabled'] if x!=n] for n in cfg['strategy']['enabled']}}; results={}
    for label,names in variants.items():
        local={**cfg,'strategy':{**cfg['strategy'],'min_votes':1 if label.startswith('only_') else cfg['strategy']['min_votes']}}; results[label]={'train':run(streams,local,news,end=cut,enabled=names)['metrics'],'test':run(streams,local,news,start=cut,enabled=names)['metrics']}
    from .news import FileNews
    news_comparison=None
    if getattr(news,'data',None) is not None:
        disabled=FileNews(None,required=False); news_comparison={'without_news_train':run(streams,cfg,disabled,end=cut)['metrics'],'without_news_test':run(streams,cfg,disabled,start=cut)['metrics'],'note':'Contrafactual offline; comparar con all.'}
    return {'split_utc':cut,'warning':'Comparación exploratoria; no optimiza ni demuestra rentabilidad.','comparisons':results,'news_ablation':news_comparison,'test_detail':run(streams,cfg,news,start=cut)}
