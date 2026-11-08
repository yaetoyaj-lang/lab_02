import csv
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from streamstats.__main__ import main

ROOT = Path(__file__).resolve().parents[1]


def run_cli(
    tmp_path: Path, *args: str | Path, module: str = "streamstats"
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", module, *map(str, args)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_cli_writes_unicode_report_in_temporary_directory(tmp_path):
    source = tmp_path / "input.jsonl"
    source.write_text(
        '{"timestamp":"2026-10-13T12:00:00Z","level":"INFO",'
        '"source":"сервис","message":"Привет"}\n',
        encoding="utf-8",
    )
    output = tmp_path / "report.json"
    result = run_cli(tmp_path, "analyze", source, "--format", "jsonl", "--output", output)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["by_source"] == {"сервис": 1}
    assert result.stdout == ""


def test_cli_default_error_and_skip_mode(tmp_path):
    source = tmp_path / "bad.jsonl"
    source.write_text("{bad}\n", encoding="utf-8")
    result = run_cli(tmp_path, "analyze", source, "--format", "jsonl")
    assert result.returncode == 2
    assert "строка 1" in result.stderr
    result = run_cli(tmp_path, "analyze", source, "--format", "jsonl", "--skip-invalid")
    assert result.returncode == 0
    assert "WARNING" in result.stderr
    assert json.loads(result.stdout)["skipped_lines"] == 1


def test_cli_preserves_existing_report_on_invalid_input(tmp_path):
    source = tmp_path / "bad.jsonl"
    source.write_text("bad", encoding="utf-8")
    output = tmp_path / "report.json"
    output.write_text("старый отчёт", encoding="utf-8")
    assert main(["analyze", str(source), "--format", "jsonl", "--output", str(output)]) == 2
    assert output.read_text(encoding="utf-8") == "старый отчёт"


def test_cli_does_not_overwrite_input(tmp_path):
    path = tmp_path / "input.csv"
    original = "timestamp,level,source,message\n"
    path.write_text(original, encoding="utf-8")
    assert main(["analyze", str(path), "--format", "csv", "--output", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == original


def test_cli_does_not_overwrite_input_through_hard_link(tmp_path: Path) -> None:
    path = tmp_path / "input.csv"
    original = "timestamp,level,source,message\n"
    path.write_text(original, encoding="utf-8")
    output = tmp_path / "report.json"
    try:
        os.link(path, output)
    except OSError as error:
        pytest.skip(f"жёсткие ссылки недоступны: {error}")
    assert main(["analyze", str(path), "--format", "csv", "--output", str(output)]) == 2
    assert path.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("bad_row", ["1" * 5000, "[" * 2000 + "0" + "]" * 2000])
def test_cli_json_limits_respect_skip_invalid(tmp_path: Path, bad_row: str) -> None:
    path = tmp_path / "input.jsonl"
    valid = '{"timestamp":"2026-10-13T12:00:00Z","level":"INFO","source":"a","message":""}'
    path.write_text(bad_row + "\n" + valid + "\n", encoding="utf-8")
    args = ("analyze", path, "--format", "jsonl")
    strict = run_cli(tmp_path, *args)
    assert strict.returncode == 2
    assert "строка 1" in strict.stderr
    assert "Traceback" not in strict.stderr

    skipping = run_cli(tmp_path, *args, "--skip-invalid")
    assert skipping.returncode == 0, skipping.stderr
    report = json.loads(skipping.stdout)
    assert report["skipped_lines"] == report["total_events"] == 1


@pytest.mark.parametrize("args", [[], ["analyze"], ["analyze", "file", "--format", "xml"]])
def test_cli_bad_arguments(args):
    assert main(args) == 2


def test_cli_help(tmp_path):
    result = run_cli(tmp_path, "--help")
    assert result.returncode == 0
    assert "analyze" in result.stdout


def test_cli_combines_filters_and_counts_invalid_lines(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    source.write_text(
        "timestamp,level,source,message\n"
        "2026-10-13T11:59:59Z,ERROR,server,too early\n"
        "2026-10-13T12:00:00Z,ERROR,server,start\n"
        "2026-10-13T12:00:01Z,INFO,server,wrong level\n"
        "2026-10-13T12:00:01Z,ERROR,cache,wrong source\n"
        "2026-10-13T12:00:02Z,ERROR,server,end\n"
        "2026-10-13T12:00:03Z,ERROR,server,too late\n"
        "2026-10-13T12:00:04Z,INVALID,cache,bad event\n",
        encoding="utf-8",
    )
    result = run_cli(
        tmp_path,
        "analyze",
        source,
        "--format",
        "csv",
        "--skip-invalid",
        "--since",
        "2026-10-13T15:00:00+03:00",
        "--until",
        "2026-10-13T12:00:02Z",
        "--level",
        "ERROR",
        "--source",
        "server",
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["total_events"] == 2
    assert report["by_source"] == {"server": 2}
    assert report["by_level"]["INFO"] == 0
    assert report["first_timestamp"] == "2026-10-13T12:00:00Z"
    assert report["last_timestamp"] == "2026-10-13T12:00:02Z"
    assert report["skipped_lines"] == 1
    assert "строка 8" in result.stderr


@pytest.mark.parametrize(
    ("bounds", "message"),
    [
        (["--since", "2026-10-13T12:00:00"], "часовой пояс"),
        (
            ["--since", "2026-10-13T12:01:00Z", "--until", "2026-10-13T12:00:00Z"],
            "--since не может быть позже --until",
        ),
    ],
)
def test_cli_rejects_invalid_time_bounds(tmp_path: Path, bounds: list[str], message: str) -> None:
    result = run_cli(tmp_path, "analyze", "missing.csv", "--format", "csv", *bounds)
    assert result.returncode == 2
    assert message in result.stderr


def test_cli_csv_report_matches_json(tmp_path: Path) -> None:
    source = tmp_path / "input.jsonl"
    source_name = "сервис,\rбаза"
    source.write_text(
        json.dumps(
            {
                "timestamp": "2026-10-13T12:00:00Z",
                "level": "ERROR",
                "source": source_name,
                "message": "ошибка",
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "report.csv"
    args = ("analyze", source, "--format", "jsonl")
    json_result = run_cli(tmp_path, *args)
    csv_result = run_cli(tmp_path, *args, "--report-format", "csv", "--output", output)
    assert json_result.returncode == csv_result.returncode == 0
    assert csv_result.stdout == ""
    report = json.loads(json_result.stdout)
    with output.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    values = {(row["section"], row["source"], row["level"]): row["value"] for row in rows}
    assert values["total_events", "", ""] == str(report["total_events"])
    assert values["by_level", "", "INFO"] == str(report["by_level"]["INFO"])
    assert values["by_source", source_name, ""] == str(report["by_source"][source_name])
    assert values["top_error_sources", source_name, "ERROR"] == "1"
    assert values["last_timestamp", "", ""] == report["last_timestamp"]


def test_custom_parser_through_registry(tmp_path: Path) -> None:
    source = tmp_path / "input.pipe"
    source.write_text(
        "2026-10-13T12:00:00Z|ERROR|сервер|a | b\n"
        "broken line\n"
        "2026-10-13T12:01:00Z|ERROR|сервер|ок\n",
        encoding="utf-8",
    )
    result = run_cli(
        tmp_path,
        "analyze",
        source,
        "--format",
        "pipe",
        "--skip-invalid",
        "--report-format",
        "csv",
        module="examples.pipe_log",
    )
    assert result.returncode == 0, result.stderr
    assert "строка 2" in result.stderr
    rows = list(csv.reader(io.StringIO(result.stdout)))
    assert ["total_events", "", "", "2"] in rows
    assert ["skipped_lines", "", "", "1"] in rows
    assert ["top_error_sources", "сервер", "ERROR", "2"] in rows
