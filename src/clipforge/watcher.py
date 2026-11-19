"""Live mode: watch a growing chat log and alert on spikes.

``watch`` tails a chat-log file that the user's own tooling is
appending to (a bot log, a chat recorder) and prints an alert the
moment chat erupts, so the streamer can note the timestamp while
it is still fresh. Detection reuses the same scoring as the
offline path; a cooldown stops one eruption alerting ten times.
"""

from __future__ import annotations

import os
import time
from collections import deque

from .chatlog import Message, parse_plain_text, parse_json_text
from .hype import score_message


class MomentAlerter:
    """Feed messages one by one; get an alert dict on a spike.

    A spike is: at least ``min_messages`` messages inside the last
    ``window`` seconds whose combined energy (1 + hype score each)
    reaches ``energy_threshold``. After an alert, ``cooldown``
    seconds must pass before the next one.
    """

    def __init__(self, window: float = 10.0, min_messages: int = 8,
                 energy_threshold: float = 25.0, cooldown: float = 45.0):
        self.window = window
        self.min_messages = min_messages
        self.energy_threshold = energy_threshold
        self.cooldown = cooldown
        self._recent: deque[tuple[Message, float]] = deque()
        self._last_alert_t: float | None = None

    def feed(self, message: Message) -> dict | None:
        energy = 1.0 + score_message(message.text).score
        self._recent.append((message, energy))
        horizon = message.t - self.window
        while self._recent and self._recent[0][0].t < horizon:
            self._recent.popleft()
        if len(self._recent) < self.min_messages:
            return None
        total = sum(e for _, e in self._recent)
        if total < self.energy_threshold:
            return None
        if (self._last_alert_t is not None
                and message.t - self._last_alert_t < self.cooldown):
            return None
        self._last_alert_t = message.t
        scored = [(m, score_message(m.text)) for m, _ in self._recent]
        keywords: dict[str, int] = {}
        for _, s in scored:
            for kw in s.keywords:
                keywords[kw] = keywords.get(kw, 0) + 1
        top = [kw for kw, _ in sorted(keywords.items(), key=lambda kv: -kv[1])[:3]]
        return {
            "peak": message.t,
            "messages_in_window": len(self._recent),
            "energy": round(total, 1),
            "keywords": top,
            "sample": message.text,
        }


def _parse_new_lines(lines: list[str], filename: str) -> list[Message]:
    text = "\n".join(lines)
    if filename.endswith((".json", ".jsonl", ".ndjson")):
        return parse_json_text(text)
    return parse_plain_text(text)


def watch_file(path: str, duration: float = 60.0, poll_interval: float = 0.5,
               on_alert=None, alerter: MomentAlerter | None = None,
               clock=time.monotonic, sleeper=time.sleep) -> list[dict]:
    """Tail *path* for *duration* seconds; alert on chat spikes.

    ``on_alert`` is called with each alert dict (default: print).
    Returns the list of alerts. ``clock``/``sleeper`` are injectable
    so tests can run the loop without real waiting.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"chat log not found: {path}")
    alerter = alerter or MomentAlerter()
    if on_alert is None:
        def on_alert(alert):
            print(f"🔥 MOMENT at {alert['peak']:.0f}s — "
                  f"{alert['messages_in_window']} messages, "
                  f"top: {', '.join(alert['keywords']) or 'hype'} "
                  f"(\"{alert['sample'][:60]}\")")
    alerts: list[dict] = []
    deadline = clock() + duration
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        fh.seek(0, os.SEEK_END)  # only new lines count as live
        while clock() < deadline:
            lines = fh.readlines()
            if lines:
                for message in _parse_new_lines(
                        [ln.rstrip("\n") for ln in lines], path):
                    alert = alerter.feed(message)
                    if alert:
                        alerts.append(alert)
                        on_alert(alert)
            else:
                sleeper(poll_interval)
    return alerts
