"""Подсчёт статистики за один проход по входным файлам"""

import logging
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from streamstats.errors import InvalidEventError, StreamStatsError
from streamstats.filters import EventFilter
from streamstats.models import Event, validate_event
from streamstats.parsers import Parser, get_parser

logger = logging.getLogger(__name__)


@dataclass
class Statistics:
    total_events: int = 0
    skipped_lines: int = 0
    by_level: Counter[str] = field(default_factory=Counter)
    by_source: Counter[str] = field(default_factory=Counter)
    errors_by_source: Counter[tuple[str, str]] = field(default_factory=Counter)
    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None

    def add(self, event: Event) -> None:
        """Обновление счётчиков по проверенному событию"""
        self.total_events += 1
        self.by_level[event.level] += 1
        self.by_source[event.source] += 1
        if event.level in ("ERROR", "CRITICAL"):
            self.errors_by_source[(event.source, event.level)] += 1

        if self.first_timestamp is None or event.timestamp < self.first_timestamp:
            self.first_timestamp = event.timestamp
        if self.last_timestamp is None or event.timestamp > self.last_timestamp:
            self.last_timestamp = event.timestamp


def _read_events(
    paths: list[Path], parser: Parser, skip_invalid: bool, statistics: Statistics
) -> Iterator[Event]:
    """Чтение и проверка записей с номерами файлов и строк"""
    for file_number, path in enumerate(paths, start=1):
        try:
            with path.open(encoding="utf-8-sig", newline="") as file:
                for line_number, data in parser(file):
                    try:
                        if isinstance(data, InvalidEventError):
                            raise data
                        event = validate_event(data)
                    except InvalidEventError as error:
                        location = f"Файл {file_number} ({path}), строка {line_number}: {error}"
                        if not skip_invalid:
                            raise type(error)(location) from error
                        statistics.skipped_lines += 1
                        logger.warning(location)
                        continue
                    yield event
        except (OSError, UnicodeError) as error:
            raise StreamStatsError(f"Файл {file_number} ({path}): {error}") from error


def analyze_files(
    paths: list[Path],
    format_name: str,
    skip_invalid: bool = False,
    *,
    event_filter: EventFilter | None = None,
) -> Statistics:
    statistics = Statistics()
    events = _read_events(paths, get_parser(format_name), skip_invalid, statistics)
    if event_filter is not None:
        events = event_filter.apply(events)
    for event in events:
        statistics.add(event)
    return statistics
