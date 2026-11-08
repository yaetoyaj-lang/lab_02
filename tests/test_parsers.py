import io
import json

import pytest

from streamstats.errors import InvalidEventError, UnsupportedFormatError
from streamstats.parsers import get_parser, parse_csv, parse_json, parse_jsonl


def test_csv_with_quoted_comma_and_unicode():
    rows = list(
        parse_csv(
            io.StringIO(
                'timestamp,level,source,message\n2026-10-13T12:00:00Z,INFO,сервис,"Привет, мир"\n'
            )
        )
    )
    assert len(rows) == 1
    assert rows[0][0] == 2
    assert rows[0][1]["message"] == "Привет, мир"


def test_csv_multiline_message_and_physical_line_numbers():
    rows = list(
        parse_csv(
            io.StringIO(
                "timestamp,level,source,message\n"
                '2026-10-13T12:00:00Z,INFO,app,"первая\nвторая"\n'
                "2026-10-13T12:00:01Z,INFO,app,ok\n"
            )
        )
    )
    assert [row[0] for row in rows] == [2, 4]
    assert rows[0][1]["message"] == "первая\nвторая"


def test_csv_wrong_number_of_fields():
    rows = list(parse_csv(io.StringIO("timestamp,level,source,message\nwrong,row\n")))
    assert isinstance(rows[0][1], InvalidEventError)


@pytest.mark.parametrize(
    "header", ["timestamp,source,message", "timestamp,level,source,message,level"]
)
def test_invalid_csv_header(header):
    rows = list(parse_csv(io.StringIO(header + "\n")))
    assert isinstance(rows[0][1], InvalidEventError)


def test_jsonl_keeps_line_numbers_and_continues_after_bad_json():
    rows = list(parse_jsonl(io.StringIO('\n{"source": "сервис"}\n{bad}\n{}\n')))
    assert [row[0] for row in rows] == [2, 3, 4]
    assert rows[0][1] == {"source": "сервис"}
    assert isinstance(rows[1][1], InvalidEventError)
    assert rows[2][1] == {}


@pytest.mark.parametrize("parser", [parse_csv, parse_jsonl])
@pytest.mark.parametrize("text", ["", "\n  \n"])
def test_empty_file(parser, text):
    assert list(parser(io.StringIO(text))) == []


def test_csv_header_only():
    assert list(parse_csv(io.StringIO("timestamp,level,source,message\n"))) == []


def test_json_array_matches_json_decoder():
    data = [{"message": 'скобки ],{ и кавычка " и слеш \\', "nested": [1, {"a": 2}]}, {}]
    text = json.dumps(data, ensure_ascii=False, indent=2)
    assert [row[1] for row in parse_json(io.StringIO(text))] == data


def test_json_array_line_numbers():
    assert list(parse_json(io.StringIO("[\n {},\n {}\n]"))) == [(2, {}), (3, {})]


def test_empty_json_array():
    assert list(parse_json(io.StringIO("[]"))) == []


@pytest.mark.parametrize("text", ["{}", "[{}", "[{},]", "[,{}]", "[] garbage"])
def test_invalid_json_array(text):
    assert any(isinstance(row[1], InvalidEventError) for row in parse_json(io.StringIO(text)))


def test_json_array_uses_bounded_reads():
    class BoundedFile(io.StringIO):
        def readline(self, size=-1):
            assert 0 < size <= 4096
            return super().readline(size)

    data = [{"message": "я" * 9000}, {"message": "вторая запись"}]
    assert [row[1] for row in parse_json(BoundedFile(json.dumps(data)))] == data


def test_unknown_parser():
    with pytest.raises(UnsupportedFormatError):
        get_parser("xml")


@pytest.mark.parametrize(
    "parser,text",
    [
        (parse_jsonl, "{}\n{}\n"),
        (parse_csv, "timestamp,level,source,message\nnow,INFO,app,ok\nnow,ERROR,app,bad\n"),
    ],
)
def test_parser_does_not_read_the_whole_file_before_first_event(parser, text):
    file = io.StringIO(text)
    records = parser(file)
    next(records)
    assert file.tell() < len(text)
