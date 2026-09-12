from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR
import math
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class Contract:
    currency: str
    contract_size: float
    quote_to_account: float
    volume_min: float
    volume_max: float
    volume_step: float
    min_stop: float
    margin_per_lot: float
    commission_roundtrip: float

    def __post_init__(self):
        values = (self.contract_size,self.quote_to_account,self.volume_min,self.volume_max,self.volume_step,self.margin_per_lot)
        if not all(math.isfinite(x) and x>0 for x in values) or self.volume_max<self.volume_min or self.min_stop<0 or self.commission_roundtrip<0 or not all(math.isfinite(x) for x in (self.min_stop,self.commission_roundtrip)):
            raise ValueError('Especificaciones de contrato inválidas')

    def loss(self, entry, stop):
        return abs(entry-stop)*self.contract_size*self.quote_to_account + self.commission_roundtrip


def size_lots(budget, loss_per_lot, contract, free_margin):
    if not all(math.isfinite(x) for x in (budget,loss_per_lot,free_margin)) or budget<=0 or loss_per_lot<=0 or free_margin<=0:
        return 0.0
    raw = min(budget/loss_per_lot, contract.volume_max, free_margin/contract.margin_per_lot)
    step = Decimal(str(contract.volume_step))
    size = float((Decimal(str(raw))/step).to_integral_value(rounding=ROUND_FLOOR)*step)
    return size if size>=contract.volume_min else 0.0


def gate(*, now, bar_close, spread, equity, day_start, positions, open_risk, cfg):
    if Path(cfg['kill_file']).exists(): return 'emergency_stop'
    if not all(math.isfinite(v) for v in (spread,equity,day_start,open_risk)) or equity<=0 or day_start<=0 or open_risk<0: return 'invalid_account'
    if now<bar_close or now-bar_close>cfg['max_age_seconds']: return 'stale_data'
    if spread<0 or spread>cfg['max_spread']: return 'spread_limit'
    if equity<=day_start*(1-cfg['daily_loss']): return 'daily_loss_limit'
    if positions>=cfg['max_positions']: return 'position_limit'
    if open_risk+equity*cfg['risk_per_trade']>equity*cfg['max_open_risk']: return 'exposure_limit'
    return None


class Journal:
    """Reserva durable antes de enviar. Estado incierto bloquea recuperación automática."""
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS intents (id TEXT PRIMARY KEY, status TEXT NOT NULL)')
        self.db.commit()

    def reserve(self, key):
        try:
            with self.db:
                self.db.execute('BEGIN IMMEDIATE')
                if self.unresolved():
                    return False
                self.db.execute('INSERT INTO intents VALUES (?, ?)', (key,'pending'))
            return True
        except sqlite3.IntegrityError:
            return False

    def unresolved(self):
        return self.db.execute("SELECT id FROM intents WHERE status IN ('pending','uncertain')").fetchall()

    def finish(self, key, status):
        if status not in ('filled','rejected','uncertain','paper'):
            raise ValueError('Estado inválido')
        with self.db:
            self.db.execute('UPDATE intents SET status=? WHERE id=?', (status,key))

    def close(self):
        self.db.close()
