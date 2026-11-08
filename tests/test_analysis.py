import json
import logging

import pytest

from streamstats.analysis import Statistics, analyze_files
from streamstats.errors import InvalidEventError, StreamStatsError
from streamstats.models import validate_event
from streamstats.report import make_report


def event(level="INFO", source="app", timestamp="2026-10-13T12:00:00Z"):
    return {"timestamp": timestamp, "level": level, "source": source, "message": "Привет"}


def write_events(path, events):
    path.write_text("\n".join(json.dumps(item) for item in events), encoding="utf-8")
    return path


@pytest.mark.parametrize("format_name", ["csv", "jsonl"])
@pytest.mark.parametrize("skip_invalid", [False, True])
def test_bad_row_in_both_modes(tmp_path, caplog, format_name, skip_invalid):
    path = tmp_path / f"input.{format_name}"
    if format_name == "csv":
        text = (
            "timestamp,level,source,message\n"
            "2026-10-13T12:00:00Z,INFO,app,ok\n"
            "wrong,row\n"
            "2026-10-13T12:00:01Z,ERROR,app,ошибка\n"
        )
    else:
        text = json.dumps(event()) + "\n{bad}\n" + json.dumps(event("ERROR"))
    path.write_text(text, encoding="utf-8")

    if skip_invalid:
        with caplog.at_level(logging.WARNING):
            statistics = analyze_files([path], format_name, True)
        assert statistics.total_events == 2
        assert statistics.skipped_lines == 1
        assert "WARNING" in caplog.text
        assert f"строка {3 if format_name == 'csv' else 2}" in caplog.text
    else:
        with pytest.raises(InvalidEventError, match="Файл 1.*строка"):
            analyze_files([path], format_name)


def test_multiple_files_and_timestamps(tmp_path):
    first = write_events(tmp_path / "first.jsonl", [event(timestamp="2026-10-13T14:00:00+03:00")])
    second = write_events(tmp_path / "second.jsonl", [event("ERROR", "база")])
    report = make_report(analyze_files([first, second], "jsonl"))
    assert report["total_events"] == 2
    assert report["by_source"] == {"app": 1, "база": 1}
    assert report["first_timestamp"] == "2026-10-13T11:00:00Z"
    assert report["last_timestamp"] == "2026-10-13T12:00:00Z"


def test_file_number_and_line_for_second_file(tmp_path):
    first = write_events(tmp_path / "first.jsonl", [event()])
    second = tmp_path / "second.jsonl"
    second.write_text("\n{broken}", encoding="utf-8")
    with pytest.raises(InvalidEventError, match="Файл 2.*строка 2"):
        analyze_files([first, second], "jsonl")


def test_top_five_separates_levels_and_prioritizes_critical_on_ties():
    statistics = Statistics()
    for source in ["a", "b", "c", "d", "e", "f"]:
        statistics.add(validate_event(event("ERROR", source)))
    statistics.add(validate_event(event("CRITICAL", "a")))
    statistics.add(validate_event(event("ERROR", "b")))
    top = make_report(statistics)["top_error_sources"]
    assert len(top) == 5
    assert top[0] == {"source": "b", "level": "ERROR", "count": 2}
    assert top[1] == {"source": "a", "level": "CRITICAL", "count": 1}
    assert top[2] == {"source": "a", "level": "ERROR", "count": 1}


def test_empty_report():
    report = make_report(Statistics())
    assert report["total_events"] == report["skipped_lines"] == 0
    assert all(count == 0 for count in report["by_level"].values())
    assert report["by_source"] == {}
    assert report["top_error_sources"] == []
    assert report["first_timestamp"] is report["last_timestamp"] is None


def test_missing_file(tmp_path):
    with pytest.raises(StreamStatsError, match="Файл 1"):
        analyze_files([tmp_path / "missing.jsonl"], "jsonl")


def test_utf8_bom(tmp_path):
    path = tmp_path / "bom.jsonl"
    path.write_text(json.dumps(event()), encoding="utf-8-sig")
    assert analyze_files([path], "jsonl").total_events == 1
