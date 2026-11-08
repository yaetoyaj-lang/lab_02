from collections.abc import Iterator

from streamstats.filters import EventFilter
from streamstats.models import Event, parse_timestamp


def test_filter_yields_match_without_reading_ahead() -> None:
    timestamp = parse_timestamp("2026-10-13T12:00:00Z")
    event = Event(timestamp, "ERROR", "server", "ошибка")

    def events() -> Iterator[Event]:
        yield Event(timestamp, "INFO", "server", "запуск")
        yield event
        raise AssertionError("фильтр запросил следующую запись слишком рано")

    filtered = EventFilter(level="ERROR").apply(events())
    assert next(filtered) == event
