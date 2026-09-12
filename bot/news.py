"""Calendario aportado por el usuario con cobertura y disponibilidad histórica."""
import json
from typing import Protocol


class NewsProvider(Protocol):
    def allowed(self, now: int, currencies: list[str]) -> tuple[bool, str]: ...


class FileNews:
    def __init__(self, path, required=True, before=1800, after=1800):
        self.required, self.before, self.after = required, before, after
        self.data = None
        if path:
            with open(path, encoding='utf-8') as f:
                self.data = json.load(f)
            for w in self.data['coverage']:
                if w['start']>=w['end'] or w['known_at']>w['start'] or not w['currencies']:
                    raise ValueError('Cobertura de noticias inválida')
            for e in self.data['events']:
                if not isinstance(e['time'], int) or not isinstance(e['known_at'], int) or not e['currency'] or e['impact'] not in ('low','medium','high'):
                    raise ValueError('Evento inválido')

    def allowed(self, now, currencies):
        if self.data is None:
            return (False, 'news_missing') if self.required else (True, 'news_disabled')
        for currency in currencies:
            covered = any(w['start']<=now-self.after and w['end']>=now+self.before and w['known_at']<=now and currency in w['currencies'] for w in self.data['coverage'])
            if not covered:
                return False, 'news_coverage_missing'
        for e in self.data['events']:
            if e['known_at']<=now and e['currency'] in currencies and e['impact']=='high' and e['time']-self.before<=now<=e['time']+self.after:
                return False, 'high_impact_news'
        return True, 'news_clear'
