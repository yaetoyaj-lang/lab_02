"""Пример формата: время|уровень|источник|сообщение"""

import sys
from collections.abc import Iterator
from typing import TextIO

from streamstats.__main__ import main
from streamstats.constants import REQUIRED_FIELDS
from streamstats.errors import InvalidEventError
from streamstats.parsers import Record, register_parser


def parse_pipe(file: TextIO) -> Iterator[Record]:
    for line_number, line in enumerate(file, start=1):
        if not line.strip():
            continue
        values = line.rstrip("\r\n").split("|", len(REQUIRED_FIELDS) - 1)
        if len(values) != len(REQUIRED_FIELDS):
            yield line_number, InvalidEventError("в записи pipe должно быть четыре поля")
            continue
        yield line_number, dict(zip(REQUIRED_FIELDS, values))


if __name__ == "__main__":
    register_parser("pipe", parse_pipe)
    sys.exit(main())
