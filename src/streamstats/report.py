"""Запись отчёта в JSON или CSV"""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import TextIO

from streamstats.analysis import Statistics
from streamstats.constants import LEVELS, REPORT_FORMATS, TOP_ERROR_LIMIT
from streamstats.models import Report, TopError


def format_timestamp(timestamp: datetime | None) -> str | None:
    if timestamp is None:
        return None
    return timestamp.isoformat().replace("+00:00", "Z")


def _error_order(item: tuple[tuple[str, str], int]) -> tuple[int, bool, str]:
    (source, level), count = item
    # Отрицательное число ставит большие счётчики первыми
    return -count, level != "CRITICAL", source


def make_report(statistics: Statistics) -> Report:
    top = sorted(statistics.errors_by_source.items(), key=_error_order)[:TOP_ERROR_LIMIT]
    top_errors: list[TopError] = []
    for (source, level), count in top:
        top_errors.append({"source": source, "level": level, "count": count})

    return {
        "total_events": statistics.total_events,
        "by_level": {level: statistics.by_level[level] for level in LEVELS},
        "by_source": dict(sorted(statistics.by_source.items())),
        "top_error_sources": top_errors,
        "first_timestamp": format_timestamp(statistics.first_timestamp),
        "last_timestamp": format_timestamp(statistics.last_timestamp),
        "skipped_lines": statistics.skipped_lines,
    }


def report_json(statistics: Statistics) -> str:
    return json.dumps(make_report(statistics), ensure_ascii=False, indent=2) + "\n"


def _write_csv(report: Report, file: TextIO) -> None:
    # Кавычки сохраняют и \r, и \n внутри имени источника
    writer = csv.writer(file, lineterminator="\n", quoting=csv.QUOTE_ALL)
    writer.writerow(("section", "source", "level", "value"))
    writer.writerow(("total_events", "", "", report["total_events"]))
    writer.writerow(("skipped_lines", "", "", report["skipped_lines"]))
    writer.writerow(("first_timestamp", "", "", report["first_timestamp"]))
    writer.writerow(("last_timestamp", "", "", report["last_timestamp"]))
    for level, count in report["by_level"].items():
        writer.writerow(("by_level", "", level, count))
    for source, count in report["by_source"].items():
        writer.writerow(("by_source", source, "", count))
    for item in report["top_error_sources"]:
        writer.writerow(("top_error_sources", item["source"], item["level"], item["count"]))


def _write_report(statistics: Statistics, file: TextIO, report_format: str) -> None:
    if report_format == "csv":
        _write_csv(make_report(statistics), file)
    else:
        file.write(report_json(statistics))


def write_report(statistics: Statistics, path: Path | None, report_format: str = "json") -> None:
    if report_format not in REPORT_FORMATS:
        raise ValueError(f"неизвестный формат отчёта: {report_format}")
    if path is None:
        _write_report(statistics, sys.stdout, report_format)
    else:
        with path.open("w", encoding="utf-8", newline="") as file:
            _write_report(statistics, file, report_format)
