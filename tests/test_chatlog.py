import pytest

from clipforge.chatlog import (
    parse_chat_text,
    parse_csv_text,
    parse_json_text,
    parse_plain_text,
    parse_timestamp,
)


def test_parse_timestamp_variants():
    assert parse_timestamp(90) == 90.0
    assert parse_timestamp("90.5") == 90.5
    assert parse_timestamp("1:30") == 90.0
    assert parse_timestamp("1:02:03") == 3723.0
    with pytest.raises(ValueError):
        parse_timestamp("soon")


def test_jsonl_with_key_variants():
    content = (
        '{"timestamp": 12.5, "author": "amy", "text": "hello"}\n'
        '{"time": "1:30", "user": "bob", "message": "GG"}\n'
        '{"offset_seconds": 95, "name": "cy", "comment": "wow"}\n'
        '{"ts": 100, "username": "di", "body": "clip it"}\n'
    )
    msgs = parse_json_text(content)
    assert [m.t for m in msgs] == [12.5, 90.0, 95.0, 100.0]
    assert msgs[1].author == "bob"
    assert msgs[3].text == "clip it"


def test_json_array():
    content = '[{"timestamp": 5, "author": "a", "text": "x"},' \
              ' {"timestamp": 9, "author": "b", "text": "y"}]'
    msgs = parse_json_text(content)
    assert len(msgs) == 2 and msgs[1].t == 9.0


def test_jsonl_malformed_lines_tolerated():
    content = (
        '{"timestamp": 1, "author": "a", "text": "ok"}\n'
        'this is not json\n'
        '{"author": "missing time", "text": "skip me"}\n'
        '{"timestamp": "bogus", "author": "a", "text": "skip me too"}\n'
        '{"timestamp": 4, "author": "b", "text": "also ok"}\n'
    )
    msgs = parse_json_text(content)
    assert [m.text for m in msgs] == ["ok", "also ok"]


def test_csv_with_header():
    content = (
        "timestamp,author,text\n"
        "10,amy,hello there\n"
        "1:30,bob,GG everyone\n"
        "95,cy,\"quoted, with comma\"\n"
    )
    msgs = parse_csv_text(content)
    assert len(msgs) == 3
    assert msgs[1].t == 90.0
    assert msgs[2].text == "quoted, with comma"


def test_csv_without_header():
    content = "10,amy,hello\n20,bob,hi again\n"
    msgs = parse_csv_text(content)
    assert [m.author for m in msgs] == ["amy", "bob"]


def test_plain_text_mmss_and_hhmmss():
    content = (
        "[12:34] amy: hello there\n"
        "[1:02:34] bob: that took forever\n"
        "a line with no timestamp\n"
        "[13:01] cy: GG\n"
    )
    msgs = parse_plain_text(content)
    assert [m.t for m in msgs] == [754.0, 3754.0, 781.0]
    assert msgs[0].author == "amy"


def test_parse_chat_text_detects_by_extension():
    msgs = parse_chat_text("[0:05] amy: hi\n[0:09] bob: yo\n", filename="chat.txt")
    assert len(msgs) == 2
    msgs = parse_chat_text('{"timestamp": 3, "author": "a", "text": "x"}',
                           filename="chat.jsonl")
    assert len(msgs) == 1


def test_parse_chat_text_sorted_output():
    content = "[0:30] a: later\n[0:05] b: earlier\n"
    msgs = parse_chat_text(content, filename="chat.log")
    assert [m.t for m in msgs] == [5.0, 30.0]
