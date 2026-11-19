"""The full pipeline: VOD + chat log in, posting pack out.

For every detected moment ClipForge creates one folder::

    clip_01_clutch/
        clip.mp4     vertical 1080x1920 cut
        thumb.jpg    frame at the peak
        post.txt     title options + caption + hashtags

plus a top-level ``pack.json`` summary and a
``POSTING-CHECKLIST.md``. Nothing is uploaded anywhere — posting
is the creator's job, on their own accounts, with their own
content. That is a design choice, not a missing feature.
"""

from __future__ import annotations

import json
import os
import re

from .chatlog import load_chatlog
from .cutter import cut_clip, grab_thumbnail, probe
from .hooks import format_post_text, generate_hooks
from .hype import Moment, detect_moments

CHECKLIST = """# Posting checklist

Before you post any clip from this pack:

- [ ] This is **my own recording**, or I have the rights/permission to clip it.
- [ ] I watched the clip end-to-end (detection is a heuristic — check the moment is real).
- [ ] I edited the title/caption so it sounds like me, not a template.
- [ ] One platform at a time, at a sensible pace — no mass or automated posting.
- [ ] No spam behaviour: no follow-for-follow, no view tricks, no engagement bait.
- [ ] The clip follows the game's and the platform's content policies.

ClipForge finds moments; it does not post, upload, or promote anything.
"""


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "moment"


def build_pack(video: str, chatlog_path: str, out_dir: str, *,
               game: str = "GTA VI", game_tags: list[str] | None = None,
               window: float = 10.0, spike_factor: float = 3.0,
               min_window_messages: int = 8,
               clip_length: float = 30.0, pre_roll: float = 8.0,
               mode: str = "crop") -> dict:
    """Run moments → cuts → hooks and write the pack to *out_dir*.

    Returns the pack summary dict (also written to pack.json).
    """
    if not os.path.isfile(video):
        raise FileNotFoundError(f"video not found: {video}")
    messages = load_chatlog(chatlog_path)
    video_info = probe(video)
    moments = detect_moments(
        messages, window=window, spike_factor=spike_factor,
        min_window_messages=min_window_messages,
        duration=video_info["duration"] or None,
    )
    os.makedirs(out_dir, exist_ok=True)
    entries = []
    for i, moment in enumerate(moments, 1):
        folder_name = f"clip_{i:02d}_{_slug(moment.category)}"
        folder = os.path.join(out_dir, folder_name)
        os.makedirs(folder, exist_ok=True)
        start = max(0.0, moment.peak - pre_roll)
        clip_info = cut_clip(video, start, clip_length,
                             os.path.join(folder, "clip.mp4"), mode=mode)
        grab_thumbnail(video, moment.peak, os.path.join(folder, "thumb.jpg"))
        hooks = generate_hooks(moment, game=game, game_tags=game_tags)
        with open(os.path.join(folder, "post.txt"), "w", encoding="utf-8") as fh:
            fh.write(format_post_text(moment, hooks))
        entries.append({
            "folder": folder_name,
            "moment": moment.to_dict(),
            "clip_start": round(start, 2),
            "clip": {k: clip_info[k] for k in ("width", "height", "codec", "duration")},
            "hooks": hooks,
        })
    summary = {
        "video": os.path.abspath(video),
        "chatlog": os.path.abspath(chatlog_path),
        "game": game,
        "moments_found": len(entries),
        "clips": entries,
    }
    with open(os.path.join(out_dir, "pack.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    with open(os.path.join(out_dir, "POSTING-CHECKLIST.md"), "w",
              encoding="utf-8") as fh:
        fh.write(CHECKLIST)
    return summary


def moments_to_json(moments: list[Moment]) -> list[dict]:
    return [m.to_dict() for m in moments]


def moments_from_json(data: list[dict]) -> list[Moment]:
    return [
        Moment(
            start=float(d["start"]), end=float(d["end"]), peak=float(d["peak"]),
            score=float(d["score"]), messages=int(d["messages"]),
            keywords=list(d.get("keywords", [])),
            category=str(d.get("category", "hype")),
            samples=list(d.get("samples", [])),
        )
        for d in data
    ]
