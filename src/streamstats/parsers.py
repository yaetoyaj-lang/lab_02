import csv
import json
from collections.abc import Callable, Iterator
from typing import TextIO

from streamstats.constants import JSON_READ_CHUNK_SIZE, REQUIRED_FIELDS
from streamstats.errors import InvalidEventError, UnsupportedFormatError

# Ошибку записи выдаём как значение, чтобы генератор мог читать дальше
Record = tuple[int, object]
# Парсер принимает открытый файл и выдаёт записи по одной
Parser = Callable[[TextIO], Iterator[Record]]


def parse_csv(file: TextIO) -> Iterator[Record]:
    """Чтение CSV с заголовком и номером начальной строки записи"""
    reader = csv.reader(file, strict=True)
    header = None
    while True:
        line_number = reader.line_num + 1
        try:
            values = next(reader)
        except StopIteration:
            return
        except csv.Error as error:
            yield line_number, InvalidEventError(f"неверный CSV: {error}")
            continue

        if not values or (len(values) == 1 and not values[0].strip()):
            continue
        if header is None:
            header = values
            if len(header) != len(set(header)) or not set(REQUIRED_FIELDS) <= set(header):
                yield line_number, InvalidEventError("неверный заголовок CSV")
                return
            continue
        if len(values) != len(header):
            yield line_number, InvalidEventError("число полей не совпадает с заголовком CSV")
            continue
        yield line_number, dict(zip(header, values))


def decode_record(text: str) -> object:
    """Разбор JSON-записи"""
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        return InvalidEventError(f"неверный JSON: {error.msg}")
    except ValueError:
        return InvalidEventError("число в JSON слишком длинное")
    except RecursionError:
        return InvalidEventError("слишком глубокая вложенность JSON")


def parse_jsonl(file: TextIO) -> Iterator[Record]:
    """Чтение JSONL по одному событию на непустую строку"""
    for line_number, line in enumerate(file, start=1):
        if line.strip():
            yield line_number, decode_record(line)


def iter_text_parts(file: TextIO) -> Iterator[tuple[int, str]]:
    """Ограничение размера чтения"""
    line_number = 1
    while True:
        part = file.readline(JSON_READ_CHUNK_SIZE)
        if not part:
            return
        yield line_number, part
        line_number += part.count("\n")


def parse_json(file: TextIO) -> Iterator[Record]:
    """Чтение JSON-массива по одному элементу (формат из обсуждения в тг)"""
    array_started = False
    array_finished = False
    in_string = False
    escaped_char = False
    nesting_depth = 0
    record_chars: list[str] = []
    start_line = 1
    after_comma = False

    for line_number, line in iter_text_parts(file):
        for char in line:
            if not array_started:
                if char.isspace():
                    continue
                if char != "[":
                    yield line_number, InvalidEventError("ожидается JSON-массив: [ ... ]")
                    return
                array_started = True
                continue
            if array_finished:
                if not char.isspace():
                    yield line_number, InvalidEventError("данные после конца JSON-массива")
                    return
                continue

            # На внешнем уровне запятая или ] заканчивает запись
            if not in_string and nesting_depth == 0 and char in ",]":
                if record_chars:
                    yield start_line, decode_record("".join(record_chars))
                    record_chars.clear()
                elif char == "," or after_comma:
                    yield line_number, InvalidEventError("пустой элемент JSON-массива")
                after_comma = char == ","
                array_finished = char == "]"
                continue

            if not record_chars and char.isspace():
                continue
            if not record_chars:
                start_line = line_number
                after_comma = False
            record_chars.append(char)

            if in_string:
                if escaped_char:
                    escaped_char = False
                elif char == "\\":
                    escaped_char = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char in "{[":
                nesting_depth += 1
            elif char in "}]":
                nesting_depth -= 1

    if not array_finished:
        yield start_line, InvalidEventError("незавершённый JSON-массив")


PARSERS: dict[str, Parser] = {"csv": parse_csv, "jsonl": parse_jsonl, "json": parse_json}


def register_parser(name: str, parser: Parser) -> None:
    """Регистрация парсера для нового формата"""
    if not name or any(char.isspace() for char in name):
        raise ValueError("имя формата должно быть непустым и без пробелов")
    if name in PARSERS:
        raise ValueError(f"формат {name!r} уже зарегистрирован")
    PARSERS[name] = parser


def get_parser(format_name: str) -> Parser:
    """Выбор парсера по названию формата"""
    if format_name not in PARSERS:
        raise UnsupportedFormatError(f"неподдерживаемый формат: {format_name}")
    return PARSERS[format_name]
