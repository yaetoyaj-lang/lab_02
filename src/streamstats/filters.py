"""Отбор событий до подсчёта статистики"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime

from streamstats.models import Event


@dataclass
class EventFilter:
    since: datetime | None = None
    until: datetime | None = None
    level: str | None = None
    source: str | None = None
    """Выдать по одному событию, которое проходит все условия"""
    def apply(self, events: Iterable[Event]) -> Iterator[Event]:
        for event in events:
            if self.since is not None and event.timestamp < self.since:
                continue
            if self.until is not None and event.timestamp > self.until:
                continue
            if self.level is not None and event.level != self.level:
                continue
            if self.source is not None and event.source != self.source:
                continue
            yield event
