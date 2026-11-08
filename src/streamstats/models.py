"""Событие, структура отчёта и проверка входных полей"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TypedDict

from streamstats.constants import LEVELS, REQUIRED_FIELDS
from streamstats.errors import InvalidEventError, InvalidTimestampError


@dataclass(frozen=True)
class Event:

    timestamp: datetime
    level: str
    source: str
    message: str


class TopError(TypedDict):

    source: str
    level: str
    count: int


class Report(TypedDict):
    """Типы значений для отчёта"""

    total_events: int
    by_level: dict[str, int]
    by_source: dict[str, int]
    top_error_sources: list[TopError]
    first_timestamp: str | None
    last_timestamp: str | None
    skipped_lines: int


def parse_timestamp(value: str) -> datetime:
    """Разбор даты ISO 8601 и перевод времени в UTC"""
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise InvalidTimestampError("timestamp должен быть датой ISO 8601") from error

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise InvalidTimestampError("timestamp должен содержать часовой пояс: Z или +03:00")
    try:
        return timestamp.astimezone(timezone.utc)
    except OverflowError as error:
        raise InvalidTimestampError("timestamp выходит за допустимый диапазон UTC") from error


def validate_event(data: object) -> Event:
    """Проверка полей и создание события"""
    if not isinstance(data, dict):
        raise InvalidEventError("событие должно быть объектом с полями")

    for field in REQUIRED_FIELDS:
        if field not in data:
            raise InvalidEventError(f"отсутствует поле {field}")
        if not isinstance(data[field], str):
            raise InvalidEventError(f"поле {field} должно быть строкой")

    if data["level"] not in LEVELS:
        raise InvalidEventError(f"неизвестный уровень {data['level']!r}")
    if not data["source"].strip():
        raise InvalidEventError("source не должен быть пустым")

    return Event(
        timestamp=parse_timestamp(data["timestamp"]),
        level=data["level"],
        source=data["source"],
        message=data["message"],
    )
