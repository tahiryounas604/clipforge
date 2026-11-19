"""Chat-log parsing.

ClipForge reads chat logs that the *user* exported from their own
stream tooling (a VOD chat replay download, a bot log, an IRC log).
Three shapes are supported:

* **JSON** — a JSON array, or JSON Lines (one object per line),
  with tolerant key variants: ``timestamp`` / ``time`` / ``offset``
  / ``offset_seconds`` / ``ts`` for the time, ``author`` / ``user``
  / ``name`` / ``username`` for the sender, and ``text`` /
  ``message`` / ``comment`` / ``body`` for the content.
* **CSV** — with a header naming those columns, or bare
  ``timestamp,author,text`` rows.
* **Plain text** — ``[12:34] user: message`` or
  ``[1:02:34] user: message`` lines (the classic IRC / chat-replay
  export shape).

Malformed lines are skipped, never fatal: real exports are messy.
Every timestamp is normalised to seconds-from-start (float).
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
from dataclasses import dataclass

_TIME_KEYS = ("timestamp", "time", "offset", "offset_seconds", "ts")
_AUTHOR_KEYS = ("author", "user", "name", "username")
_TEXT_KEYS = ("text", "message", "comment", "body")

_TEXT_LINE_RE = re.compile(
    r"^\[(?P<t>\d{1,3}:\d{2}(?::\d{2})?)\]\s+(?P<author>[^:]+?):\s*(?P<text>.*)$"
)


@dataclass(frozen=True)
class Message:
    """One chat message, ``t`` seconds after the stream started."""

    t: float
    author: str
    text: str


def parse_timestamp(value) -> float:
    """Normalise a timestamp value to seconds (float).

    Accepts numbers (seconds), numeric strings, ``MM:SS`` and
    ``H:MM:SS`` strings. Raises ``ValueError`` on anything else.
    """
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        raise ValueError("empty timestamp")
    try:
        return float(s)
    except ValueError:
        pass
    parts = s.split(":")
    if len(parts) in (2, 3):
        try:
            nums = [float(p) for p in parts]
        except ValueError:
            raise ValueError(f"unparseable timestamp: {value!r}") from None
        if len(nums) == 2:
            return nums[0] * 60 + nums[1]
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    raise ValueError(f"unparseable timestamp: {value!r}")


def _pick(record: dict, keys) -> object:
    for key in keys:
        if key in record and record[key] is not None:
            return record[key]
    return None


def message_from_record(record) -> Message | None:
    """Build a Message from a decoded JSON object, or None."""
    if not isinstance(record, dict):
        return None
    raw_t = _pick(record, _TIME_KEYS)
    raw_text = _pick(record, _TEXT_KEYS)
    if raw_t is None or raw_text is None:
        return None
    try:
        t = parse_timestamp(raw_t)
    except ValueError:
        return None
    author = _pick(record, _AUTHOR_KEYS)
    return Message(t=t, author=str(author) if author else "unknown",
                   text=str(raw_text))


def parse_json_text(content: str) -> list[Message]:
    """Parse a JSON array or JSON-Lines chat export."""
    stripped = content.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, list):
            return [m for m in (message_from_record(r) for r in data) if m]
    messages = []
    for line in stripped.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = message_from_record(record)
        if msg:
            messages.append(msg)
    return messages


def parse_csv_text(content: str) -> list[Message]:
    """Parse a CSV chat export (header or bare timestamp,author,text)."""
    messages = []
    reader = csv.reader(io.StringIO(content))
    rows = [row for row in reader if row and any(c.strip() for c in row)]
    if not rows:
        return []
    first = [c.strip().lower() for c in rows[0]]
    start = 0
    col = {"t": 0, "author": 1, "text": 2}
    if any(name in first for name in _TIME_KEYS):
        start = 1
        for idx, name in enumerate(first):
            if name in _TIME_KEYS:
                col["t"] = idx
            elif name in _AUTHOR_KEYS:
                col["author"] = idx
            elif name in _TEXT_KEYS:
                col["text"] = idx
    for row in rows[start:]:
        if len(row) <= max(col.values()):
            # Text containing commas must be quoted in CSV; a short
            # row here is malformed, so skip it.
            if len(row) < 3:
                continue
        try:
            t = parse_timestamp(row[col["t"]])
        except (ValueError, IndexError):
            continue
        author = row[col["author"]].strip() if col["author"] < len(row) else "unknown"
        # Any extra columns belong to the message text (unquoted commas).
        text = ",".join(row[col["text"]:]).strip()
        if text:
            messages.append(Message(t=t, author=author or "unknown", text=text))
    return messages


def parse_plain_text(content: str) -> list[Message]:
    """Parse ``[MM:SS] user: message`` / ``[H:MM:SS] user: message`` lines."""
    messages = []
    for line in content.splitlines():
        m = _TEXT_LINE_RE.match(line.strip())
        if not m:
            continue
        try:
            t = parse_timestamp(m.group("t"))
        except ValueError:
            continue
        messages.append(Message(t=t, author=m.group("author").strip(),
                                text=m.group("text").strip()))
    return messages


_PARSERS = {
    ".json": parse_json_text,
    ".jsonl": parse_json_text,
    ".ndjson": parse_json_text,
    ".csv": parse_csv_text,
    ".txt": parse_plain_text,
    ".log": parse_plain_text,
}


def parse_chat_text(content: str, filename: str = "") -> list[Message]:
    """Parse chat-log text, choosing the parser by extension/content."""
    ext = os.path.splitext(filename)[1].lower()
    parser = _PARSERS.get(ext)
    if parser is not None:
        result = parser(content)
        if result:
            return sorted(result, key=lambda m: m.t)
    # Unknown extension or empty result: try each parser in turn.
    for candidate in (parse_json_text, parse_csv_text, parse_plain_text):
        result = candidate(content)
        if result:
            return sorted(result, key=lambda m: m.t)
    return []


def load_chatlog(path: str) -> list[Message]:
    """Load and parse a chat-log file into time-sorted Messages."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"chat log not found: {path}")
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read()
    return parse_chat_text(content, filename=path)
