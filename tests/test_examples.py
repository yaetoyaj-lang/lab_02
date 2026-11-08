from pathlib import Path

import pytest

from streamstats.analysis import analyze_files
from streamstats.report import make_report

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.mark.parametrize("format_name", ["csv", "jsonl", "json"])
def test_teachers_sample(format_name):
    report = make_report(analyze_files([EXAMPLES / f"logs.{format_name}"], format_name))
    assert report["total_events"] == 10
    assert report["by_level"] == {
        "DEBUG": 2,
        "INFO": 3,
        "WARNING": 2,
        "ERROR": 2,
        "CRITICAL": 1,
    }
    assert len(report["by_source"]) == 9
    assert report["by_source"]["auth.service"] == 2
    assert report["skipped_lines"] == 0
    assert report["first_timestamp"] == "2026-10-13T12:00:00Z"
    assert report["last_timestamp"] == "2026-10-13T12:00:09Z"
    assert report["top_error_sources"] == [
        {"source": "system.monitor", "level": "CRITICAL", "count": 1},
        {"source": "api.gateway", "level": "ERROR", "count": 1},
        {"source": "database.client", "level": "ERROR", "count": 1},
    ]


def test_all_formats_produce_identical_reports():
    reports = [
        make_report(analyze_files([EXAMPLES / f"logs.{format_name}"], format_name))
        for format_name in ("csv", "jsonl", "json")
    ]
    assert reports[0] == reports[1] == reports[2]


def test_two_csv_files_are_merged():
    path = EXAMPLES / "logs.csv"
    report = make_report(analyze_files([path, path], "csv"))
    assert report["total_events"] == 20
    assert report["by_source"]["auth.service"] == 4


def test_invalid_example_in_skip_mode():
    report = make_report(analyze_files([EXAMPLES / "invalid.jsonl"], "jsonl", True))
    assert report["total_events"] == 2
    assert report["skipped_lines"] == 2
    assert report["by_level"]["ERROR"] == 0
