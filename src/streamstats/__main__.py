"""Обработка py -m streamstats"""

import argparse
import logging
import sys
from pathlib import Path
from typing import NoReturn

from streamstats.analysis import analyze_files
from streamstats.constants import LEVELS, REPORT_FORMATS
from streamstats.errors import CLIConfigurationError, StreamStatsError
from streamstats.filters import EventFilter
from streamstats.models import parse_timestamp
from streamstats.parsers import PARSERS
from streamstats.report import write_report


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise CLIConfigurationError(message)


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Потоковый анализатор файлов событий")
    commands = parser.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser("analyze", help="посчитать статистику событий")
    analyze.add_argument("inputs", nargs="+", type=Path, metavar="INPUT")
    analyze.add_argument("--format", required=True, metavar="{" + ",".join(PARSERS) + "}")
    analyze.add_argument("--output", type=Path, metavar="REPORT")
    analyze.add_argument("--report-format", choices=REPORT_FORMATS, default="json")
    analyze.add_argument("--since", type=parse_timestamp, help="начало периода включительно")
    analyze.add_argument("--until", type=parse_timestamp, help="конец периода включительно")
    analyze.add_argument("--level", choices=LEVELS, help="оставить события этого уровня")
    analyze.add_argument("--source", help="оставить события этого источника")
    analyze.add_argument("--skip-invalid", action="store_true", help="пропускать неверные записи")
    return parser


def _check_output(inputs: list[Path], output: Path) -> None:
    output = output.resolve()
    output_exists = output.exists()
    for path in inputs:
        same_path = path.resolve() == output
        if same_path or (output_exists and path.exists() and output.samefile(path)):
            raise CLIConfigurationError("отчёт не должен перезаписывать входной файл")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    try:
        args = build_parser().parse_args(argv)
        if args.output is not None:
            _check_output(args.inputs, args.output)
        if args.since is not None and args.until is not None and args.since > args.until:
            raise CLIConfigurationError("--since не может быть позже --until")
        event_filter = EventFilter(
            since=args.since, until=args.until, level=args.level, source=args.source
        )
        statistics = analyze_files(
            args.inputs, args.format, args.skip_invalid, event_filter=event_filter
        )
        write_report(statistics, args.output, args.report_format)
    except (StreamStatsError, OSError, UnicodeError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
