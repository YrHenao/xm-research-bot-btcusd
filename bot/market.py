from dataclasses import dataclass
import csv
import math


@dataclass(frozen=True)
class Bar:
    time: int  # apertura en reloj exportado del servidor MT4; OHLC bid
    open: float
    high: float
    low: float
    close: float
    spread: float  # unidades de precio, no puntos


def validate(bars):
    for i, b in enumerate(bars):
        if not all(math.isfinite(v) for v in (b.open, b.high, b.low, b.close, b.spread)):
            raise ValueError('Datos no finitos')
        if b.time % 60 or b.low <= 0 or b.spread < 0 or not b.low <= min(b.open, b.close) <= max(b.open, b.close) <= b.high:
            raise ValueError('Vela M1 inválida')
        if i and b.time <= bars[i-1].time:
            raise ValueError('Tiempos duplicados o desordenados')
    return bars


def read_bars(path):
    with open(path, newline='', encoding='utf-8') as f:
        return validate([Bar(int(r['time']), *(float(r[k]) for k in ('open','high','low','close','spread'))) for r in csv.DictReader(f)])


def aggregate(bars, minutes):
    """Solo bloques completos y contiguos; nunca usa un marco superior abierto."""
    groups = {}
    for b in bars:
        groups.setdefault(b.time // (minutes*60), []).append(b)
    result = []
    for key, chunk in groups.items():
        if len(chunk) == minutes and chunk[0].time == key*minutes*60 and chunk[-1].time == (key+1)*minutes*60-60:
            result.append(Bar(chunk[0].time, chunk[0].open, max(x.high for x in chunk), min(x.low for x in chunk), chunk[-1].close, chunk[-1].spread))
    return result
