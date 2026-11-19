"""ClipForge command line.

Subcommands:

* ``moments`` — find chat-hype moments in a chat log.
* ``cut``     — cut vertical clips for moments from a moments JSON.
* ``hooks``   — generate title/caption/hashtag drafts for moments.
* ``pack``    — full pipeline: VOD + chat log → posting pack.
* ``watch``   — tail a growing chat log and alert on spikes live.

ClipForge only ever reads files you give it. There is no download
command and no posting command — on purpose.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .chatlog import load_chatlog
from .cutter import cut_clip, grab_thumbnail
from .hooks import format_post_text, generate_hooks
from .hype import detect_moments
from .pack import build_pack, moments_from_json, moments_to_json
from .watcher import watch_file


def _fmt_ts(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _load_moments(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        return moments_from_json(json.load(fh))


def cmd_moments(args) -> int:
    messages = load_chatlog(args.chatlog)
    moments = detect_moments(
        messages, window=args.window, spike_factor=args.spike_factor,
        min_window_messages=args.min_messages,
    )
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(moments_to_json(moments), fh, indent=2)
    print(f"{len(messages)} messages parsed, {len(moments)} moment(s) found.")
    for m in moments:
        print(f"  {_fmt_ts(m.peak)}  score {m.score:5.1f}  {m.category:6s} "
              f"{m.messages} msgs  top: {', '.join(m.keywords) or '—'}")
    return 0


def cmd_cut(args) -> int:
    moments = _load_moments(args.moments)
    os.makedirs(args.out_dir, exist_ok=True)
    for i, m in enumerate(moments, 1):
        start = max(0.0, m.peak - args.pre_roll)
        out = os.path.join(args.out_dir, f"clip_{i:02d}.mp4")
        info = cut_clip(args.video, start, args.length, out, mode=args.mode)
        grab_thumbnail(args.video, m.peak,
                       os.path.join(args.out_dir, f"clip_{i:02d}.jpg"))
        print(f"clip_{i:02d}.mp4  {info['width']}x{info['height']}  "
              f"{info['duration']:.1f}s  (peak {_fmt_ts(m.peak)})")
    return 0


def cmd_hooks(args) -> int:
    moments = _load_moments(args.moments)
    tags = args.tags.split(",") if args.tags else None
    results = []
    for i, m in enumerate(moments, 1):
        hooks = generate_hooks(m, game=args.game, game_tags=tags)
        results.append({"moment": m.to_dict(), "hooks": hooks})
        print(f"--- moment {i} (peak {_fmt_ts(m.peak)}, {m.category}) ---")
        print(format_post_text(m, hooks))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2)
    return 0


def cmd_pack(args) -> int:
    tags = args.tags.split(",") if args.tags else None
    summary = build_pack(
        args.video, args.chatlog, args.out,
        game=args.game, game_tags=tags,
        window=args.window, spike_factor=args.spike_factor,
        min_window_messages=args.min_messages,
        clip_length=args.length, pre_roll=args.pre_roll, mode=args.mode,
    )
    print(f"Pack written to {args.out}: {summary['moments_found']} clip(s).")
    for entry in summary["clips"]:
        print(f"  {entry['folder']}/  score {entry['moment']['score']:.0f}  "
              f"{entry['moment']['category']}")
    print("Read POSTING-CHECKLIST.md before posting anything.")
    return 0


def cmd_watch(args) -> int:
    alerts = watch_file(args.chatlog, duration=args.duration)
    print(f"Watch ended: {len(alerts)} moment alert(s).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clipforge",
        description="Turn your OWN stream VODs into vertical clips with "
                    "chat-hype moment detection. Input files only: no "
                    "downloading, no posting.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("moments", help="find chat-hype moments in a chat log")
    p.add_argument("chatlog")
    p.add_argument("--window", type=float, default=10.0)
    p.add_argument("--spike-factor", type=float, default=3.0)
    p.add_argument("--min-messages", type=int, default=8)
    p.add_argument("--out", help="write moments JSON here")
    p.set_defaults(func=cmd_moments)

    p = sub.add_parser("cut", help="cut vertical clips from a moments JSON")
    p.add_argument("video")
    p.add_argument("--moments", required=True)
    p.add_argument("--out-dir", default="clips")
    p.add_argument("--length", type=float, default=30.0)
    p.add_argument("--pre-roll", type=float, default=8.0)
    p.add_argument("--mode", choices=["crop", "blurpad"], default="crop")
    p.set_defaults(func=cmd_cut)

    p = sub.add_parser("hooks", help="title/caption/hashtag drafts for moments")
    p.add_argument("--moments", required=True)
    p.add_argument("--game", default="GTA VI")
    p.add_argument("--tags", help="comma-separated hashtags (overrides defaults)")
    p.add_argument("--out", help="write hooks JSON here")
    p.set_defaults(func=cmd_hooks)

    p = sub.add_parser("pack", help="full pipeline: VOD + chat log → pack")
    p.add_argument("video")
    p.add_argument("chatlog")
    p.add_argument("--out", default="clipforge-pack")
    p.add_argument("--game", default="GTA VI")
    p.add_argument("--tags", help="comma-separated hashtags (overrides defaults)")
    p.add_argument("--window", type=float, default=10.0)
    p.add_argument("--spike-factor", type=float, default=3.0)
    p.add_argument("--min-messages", type=int, default=8)
    p.add_argument("--length", type=float, default=30.0)
    p.add_argument("--pre-roll", type=float, default=8.0)
    p.add_argument("--mode", choices=["crop", "blurpad"], default="crop")
    p.set_defaults(func=cmd_pack)

    p = sub.add_parser("watch", help="tail a growing chat log, alert on spikes")
    p.add_argument("chatlog")
    p.add_argument("--duration", type=float, default=60.0)
    p.set_defaults(func=cmd_watch)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
