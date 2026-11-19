"""Chat-hype scoring and spike (moment) detection.

The idea is simple and deliberately transparent: when something
big happens on stream, chat *erupts* — message rate jumps far above
its baseline and the messages fill with hype signals (``W``, ``GG``,
``OMG``, ``CLIP IT``, all-caps shouting, ``!!!!``, ``LOOOOL``).
ClipForge scores every message, bins the scores per second, and
reports the windows whose traffic is a configurable multiple of
the stream's own baseline.

This is a heuristic, not an oracle: a loud chat usually means a
good moment, but raids, arguments and bot spam are loud too. The
scores are a shortlist for a human, not a guarantee.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

from .chatlog import Message

# keyword -> (weight, category). Matched case-insensitively on word
# boundaries (or as whole phrases). Categories drive hook templates.
KEYWORDS: dict[str, tuple[float, str]] = {
    "clip it": (3.0, "hype"),
    "clip that": (3.0, "hype"),
    "pog": (2.0, "hype"),
    "poggers": (2.0, "hype"),
    "omg": (2.0, "hype"),
    "wow": (1.5, "hype"),
    "insane": (2.0, "clutch"),
    "clutch": (2.5, "clutch"),
    "gg": (1.5, "clutch"),
    "no way": (2.0, "chaos"),
    "wtf": (2.0, "chaos"),
    "what": (0.5, "chaos"),
    "lol": (1.5, "funny"),
    "lmao": (2.0, "funny"),
    "lmfao": (2.0, "funny"),
    "fail": (1.5, "funny"),
    "lets go": (2.0, "hype"),
    "let's go": (2.0, "hype"),
    "hype": (1.5, "hype"),
    "goat": (2.0, "clutch"),
    "crazy": (1.5, "chaos"),
    "fire": (1.0, "hype"),
    "w": (1.0, "hype"),
}

_KEYWORD_RES = {
    word: re.compile(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])")
    for word in KEYWORDS
}
_REPEAT_RE = re.compile(r"(.)\1{2,}")
_TOKEN_RE = re.compile(r"[A-Za-z]{2,}")


@dataclass
class MessageScore:
    score: float
    keywords: list[str]
    category: str | None


def score_message(text: str) -> MessageScore:
    """Score one chat message for hype signals (pure)."""
    lowered = text.lower()
    score = 0.0
    hits: list[str] = []
    category_votes: dict[str, float] = {}
    for word, (weight, category) in KEYWORDS.items():
        if _KEYWORD_RES[word].search(lowered):
            score += weight
            hits.append(word)
            category_votes[category] = category_votes.get(category, 0.0) + weight
    # All-caps shouting: fraction of letters that are uppercase.
    letters = [c for c in text if c.isalpha()]
    if len(letters) >= 4:
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio >= 0.7:
            score += 1.5
    # Exclamation density.
    score += min(text.count("!") * 0.25, 1.0)
    # Repeated-character bursts: "LOOOOL", "WOOOO", "!!!!" style.
    if _REPEAT_RE.search(text):
        score += 0.75
    # A run of short all-caps tokens ("W W W", "GG GG") reads as hype.
    tokens = _TOKEN_RE.findall(text)
    caps_tokens = [tok for tok in tokens if tok.isupper()]
    if len(caps_tokens) >= 2:
        score += 0.5
    category = None
    if category_votes:
        category = max(category_votes.items(), key=lambda kv: kv[1])[0]
    return MessageScore(score=score, keywords=hits, category=category)


@dataclass
class Moment:
    """A detected chat spike, times in seconds from stream start."""

    start: float
    end: float
    peak: float
    score: float            # 0..100, relative to this stream's baseline
    messages: int           # messages inside the window
    keywords: list[str]     # most frequent hype keywords in the window
    category: str           # funny / clutch / chaos / hype
    samples: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "start": round(self.start, 2),
            "end": round(self.end, 2),
            "peak": round(self.peak, 2),
            "score": round(self.score, 1),
            "messages": self.messages,
            "keywords": list(self.keywords),
            "category": self.category,
            "samples": list(self.samples),
        }


def _top_keywords(scored: list[tuple[Message, MessageScore]], limit: int = 5):
    counts: dict[str, int] = {}
    for _, s in scored:
        for kw in s.keywords:
            counts[kw] = counts.get(kw, 0) + 1
    return [kw for kw, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:limit]]


def _dominant_category(scored: list[tuple[Message, MessageScore]]) -> str:
    votes: dict[str, float] = {}
    for _, s in scored:
        if s.category:
            votes[s.category] = votes.get(s.category, 0.0) + 1.0
    if not votes:
        return "hype"
    return max(votes.items(), key=lambda kv: kv[1])[0]


def detect_moments(
    messages: list[Message],
    window: float = 10.0,
    spike_factor: float = 3.0,
    min_window_messages: int = 8,
    min_gap: float = 30.0,
    duration: float | None = None,
) -> list[Moment]:
    """Detect chat spikes in *messages* (pure).

    A per-second energy series (1 + hype score per message) is
    summed over a sliding *window*. The baseline is the median
    per-second energy — what this stream's chat normally feels
    like — so a window counts as a spike when its energy is at
    least *spike_factor* times the expected baseline window energy
    **and** it holds at least *min_window_messages* raw messages.
    Contiguous spiking regions merge into one moment, peaked at the
    busiest window; moments closer than *min_gap* seconds merge
    too. (Per-second, not per-window, baseline: on a short VOD a
    single eruption fills most windows, which would poison a
    per-window median.)
    """
    if not messages:
        return []
    scored = [(m, score_message(m.text)) for m in messages]
    if duration is None:
        duration = max(m.t for m in messages) + 1.0
    n_seconds = max(int(duration), 1)
    energy = [0.0] * (n_seconds + 1)
    counts = [0] * (n_seconds + 1)
    for m, s in scored:
        idx = min(int(m.t), n_seconds)
        energy[idx] += 1.0 + s.score
        counts[idx] += 1
    win = max(int(window), 1)
    window_energy = []
    window_msgs = []
    run_e = 0.0
    run_c = 0
    for i in range(n_seconds + 1):
        run_e += energy[i]
        run_c += counts[i]
        if i >= win:
            run_e -= energy[i - win]
            run_c -= counts[i - win]
        if i >= win - 1:
            window_energy.append(run_e)
            window_msgs.append(run_c)
    if not window_energy:
        return []
    baseline_per_second = statistics.median(energy)
    expected_window = baseline_per_second * win
    threshold = max(expected_window * spike_factor, float(min_window_messages))
    # Contiguous regions where the window energy clears the bar.
    regions: list[tuple[int, int]] = []
    start = None
    for i, e in enumerate(window_energy):
        hot = e >= threshold and window_msgs[i] >= min_window_messages
        if hot and start is None:
            start = i
        elif not hot and start is not None:
            regions.append((start, i - 1))
            start = None
    if start is not None:
        regions.append((start, len(window_energy) - 1))
    moments: list[Moment] = []
    for r_start, r_end in regions:
        peak_i = max(range(r_start, r_end + 1), key=lambda i: window_energy[i])
        peak_energy = window_energy[peak_i]
        peak_t = float(peak_i + win - 1)
        win_start = peak_t - win + 1
        in_window = [(m, s) for m, s in scored if win_start <= m.t <= peak_t + 1]
        score = min(100.0, 100.0 * peak_energy / (peak_energy + threshold))
        moments.append(Moment(
            start=win_start,
            end=peak_t + 1,
            peak=peak_t,
            score=score,
            messages=len(in_window),
            keywords=_top_keywords(in_window),
            category=_dominant_category(in_window),
            samples=[m.text for m, _ in in_window[:3]],
        ))
    # Merge moments that sit closer than min_gap (same eruption).
    merged: list[Moment] = []
    for moment in moments:
        if merged and moment.start - merged[-1].end < min_gap:
            prev = merged[-1]
            if moment.score > prev.score:
                merged[-1] = Moment(
                    start=prev.start, end=moment.end, peak=moment.peak,
                    score=moment.score, messages=prev.messages + moment.messages,
                    keywords=moment.keywords or prev.keywords,
                    category=moment.category, samples=moment.samples or prev.samples,
                )
            else:
                prev.end = moment.end
                prev.messages += moment.messages
        else:
            merged.append(moment)
    return merged
