"""Heurísticas medibles. Cada función recibe exclusivamente un prefijo cerrado."""
from .market import aggregate

NAMES = ('levels', 'trend', 'fibonacci', 'three_lines', 'triangle', 'head_shoulders')


def pivots(bars, wing):
    out=[]
    for i in range(wing,len(bars)-wing):
        neighbors=bars[i-wing:i]+bars[i+1:i+wing+1]
        if all(bars[i].high>b.high for b in neighbors): out.append((i,bars[i].high,'H',i+wing))
        if all(bars[i].low<b.low for b in neighbors): out.append((i,bars[i].low,'L',i+wing))
    return out


def line(points):
    xs,ys=[p[0] for p in points],[p[1] for p in points]; xm,ym=sum(xs)/len(xs),sum(ys)/len(ys)
    slope=sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/sum((x-xm)**2 for x in xs)
    return slope,ym-slope*xm


def analyze(bars,cfg):
    out={name:{'side':0,'detail':{}} for name in NAMES}
    if len(bars)<cfg['warmup']: return out
    bars=bars[-cfg['lookback']:]; p=pivots(bars[:-1],cfg['pivot_wing']); highs=[x for x in p if x[2]=='H']; lows=[x for x in p if x[2]=='L']
    i,c,prev=len(bars)-1,bars[-1].close,bars[-2].close
    atr=sum(max(b.high-b.low,abs(b.high-a.close),abs(b.low-a.close)) for a,b in zip(bars[-15:-1],bars[-14:]))/14
    tol=max(atr*cfg['tolerance_atr'],1e-9); levels=[]
    for pt in sorted(p,key=lambda x:x[1]):
        if levels and abs(pt[1]-levels[-1][0])<=tol:
            value,count=levels[-1]; levels[-1]=((value*count+pt[1])/(count+1),count+1)
        else: levels.append((pt[1],1))
    eligible=[v for v,n in levels if n>=cfg['level_contacts']]; up=any(prev<=v+tol<c for v in eligible); down=any(c<v-tol<=prev for v in eligible)
    out['levels']={'side':int(up)-int(down),'detail':{'clusters':levels,'tolerance':tol}}
    trend=0
    if len(highs)>=2 and len(lows)>=2: trend=int(highs[-1][1]>highs[-2][1] and lows[-1][1]>lows[-2][1])-int(highs[-1][1]<highs[-2][1] and lows[-1][1]<lows[-2][1])
    out['trend']={'side':trend,'detail':{'last_highs':highs[-2:],'last_lows':lows[-2:]}}
    if highs and lows:
        h,l=highs[-1],lows[-1]
        if h[1]>l[1]:
            rising=h[0]>l[0]; fib=[h[1]-r*(h[1]-l[1]) if rising else l[1]+r*(h[1]-l[1]) for r in cfg['fib_ratios']]
            touch=any(bars[-1].low-tol<=v<=bars[-1].high+tol and (c>v and c>prev if rising else c<v and c<prev) for v in fib)
            out['fibonacci']={'side':(1 if rising else -1) if touch else 0,'detail':{'levels':fib,'anchors':[l,h]}}
    if len(highs)>=3 and len(lows)>=3:
        sh,bh=line(highs[-3:]); sl,bl=line(lows[-3:]); upper,lower=sh*i+bh,sl*i+bl
        residual=max([abs(y-(sh*x+bh)) for x,y,*_ in highs[-3:]]+[abs(y-(sl*x+bl)) for x,y,*_ in lows[-3:]])
        contacts_h=sum(abs(b.high-(sh*j+bh))<=tol for j,b in enumerate(bars) if j>=highs[-3][0]); contacts_l=sum(abs(b.low-(sl*j+bl))<=tol for j,b in enumerate(bars) if j>=lows[-3][0])
        side=int(abs(bars[-1].low-lower)<=tol and c>lower and c>prev)-int(abs(bars[-1].high-upper)<=tol and c<upper and c<prev)
        out['three_lines']={'side':side if residual<=tol else 0,'detail':{'upper':[sh,bh],'lower':[sl,bl],'contacts':[contacts_h,contacts_l],'residual':residual}}
        converging=sh<sl and upper>lower and residual<=tol; breakout=int(c>upper+tol and prev<=sh*(i-1)+bh+tol)-int(c<lower-tol and prev>=sl*(i-1)+bl-tol)
        out['triangle']={'side':breakout if converging else 0,'detail':{'converging':converging,'upper':upper,'lower':lower}}
    alt=[]
    for pt in p:
        if alt and alt[-1][2]==pt[2]:
            if (pt[1]>alt[-1][1])==(pt[2]=='H'): alt[-1]=pt
        else: alt.append(pt)
    if len(alt)>=5:
        a,b,h,d,e=alt[-5:]; sign=-1 if a[2]=='H' else 1; shoulder_ok=abs(a[1]-e[1])<=cfg['shoulder_tolerance_atr']*atr
        head_ok=(h[1]-max(a[1],e[1])>tol) if sign==-1 else (min(a[1],e[1])-h[1]>tol); sn,bn=line([b,d]); neck=sn*i+bn
        crossed=c<neck-tol and prev>=sn*(i-1)+bn-tol if sign==-1 else c>neck+tol and prev<=sn*(i-1)+bn+tol
        out['head_shoulders']={'side':sign if shoulder_ok and head_ok and crossed else 0,'detail':{'pivots':[a,b,h,d,e],'neckline':neck,'shoulders_valid':shoulder_ok,'head_valid':head_ok}}
    return out


def decide(bars,cfg,enabled=None):
    signals=analyze(bars,cfg); names=cfg['enabled'] if enabled is None else enabled; votes=[signals[n]['side'] for n in names]; score=sum(votes)
    side=(1 if score>0 else -1) if abs(score)>=cfg['min_votes'] else 0; filters={}
    for minutes in cfg['trend_frames']:
        higher=aggregate(bars,minutes); n=cfg['trend_period']
        direction=0 if len(higher)<n+1 else (1 if higher[-1].close>sum(b.close for b in higher[-n:])/n and higher[-1].close>higher[-n-1].close else -1 if higher[-1].close<sum(b.close for b in higher[-n:])/n and higher[-1].close<higher[-n-1].close else 0)
        filters[str(minutes)]=direction
        if direction!=side: side=0
    return side,{'signals':signals,'score':score,'filters':filters}
