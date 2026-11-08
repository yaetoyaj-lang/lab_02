import pytest

from streamstats.errors import InvalidEventError, InvalidTimestampError
from streamstats.models import validate_event


def valid_data():
    return {
        "timestamp": "2026-10-13T15:00:00+03:00",
        "level": "INFO",
        "source": "учебный.сервис",
        "message": "Привет, мир!",
    }


def test_valid_event_and_utc_conversion():
    event = validate_event(valid_data())
    assert event.timestamp.isoformat() == "2026-10-13T12:00:00+00:00"
    assert event.message == "Привет, мир!"


@pytest.mark.parametrize("field", ["timestamp", "level", "source", "message"])
def test_missing_field(field):
    data = valid_data()
    del data[field]
    with pytest.raises(InvalidEventError, match=field):
        validate_event(data)


@pytest.mark.parametrize("field", ["timestamp", "level", "source", "message"])
def test_fields_must_be_strings(field):
    data = valid_data()
    data[field] = 123
    with pytest.raises(InvalidEventError, match=field):
        validate_event(data)


@pytest.mark.parametrize("source", ["", "   "])
def test_empty_source(source):
    data = valid_data()
    data["source"] = source
    with pytest.raises(InvalidEventError, match="source"):
        validate_event(data)


@pytest.mark.parametrize(
    "timestamp",
    ["не дата", "2026-10-13T12:00:00", "2026-02-30T12:00:00Z", "0001-01-01T00:00:00+03:00"],
)
def test_invalid_timestamp(timestamp):
    data = valid_data()
    data["timestamp"] = timestamp
    with pytest.raises(InvalidTimestampError):
        validate_event(data)


def test_unknown_level():
    data = valid_data()
    data["level"] = "error"
    with pytest.raises(InvalidEventError, match="уровень"):
        validate_event(data)


def test_empty_message_is_allowed():
    data = valid_data()
    data["message"] = ""
    assert validate_event(data).message == ""


def test_non_object():
    with pytest.raises(InvalidEventError):
        validate_event([1, 2, 3])
