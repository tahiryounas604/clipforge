# ClipForge

# GTA VI — Rockstar made the game. ClipForge makes the clips.

*GTA VI is breaking the internet. ClipForge turns YOUR streams into the clips everyone watches.*

[![tests](https://img.shields.io/badge/tests-36%20passing-brightgreen)](https://github.com/tahiryounas604/clipforge)
[![clips](https://img.shields.io/badge/clips-1080x1920%209%3A16-blue)](https://github.com/tahiryounas604/clipforge)
[![detection](https://img.shields.io/badge/detection-chat--hype-orange)](https://github.com/tahiryounas604/clipforge)
[![license](https://img.shields.io/badge/license-GPL--3.0-green)](LICENSE)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](https://github.com/tahiryounas604/clipforge)

ClipForge finds the moments your chat exploded in **your own stream recordings**, cuts them into ready-to-post vertical 1080×1920 clips with ffmpeg, and packs each one with a thumbnail, title options, a caption and hashtags.

## What it does

You give ClipForge two files you already own — a stream VOD/recording and the chat log for that stream — and it gives you back a pack of clips:

```
clipforge pack vod.mp4 chat.jsonl
```

```
clipforge-pack/
├── POSTING-CHECKLIST.md      read this before posting anything
├── pack.json                 machine-readable summary
└── clip_01_clutch/
    ├── clip.mp4              vertical 1080x1920, ready to post
    ├── thumb.jpg             frame at the peak of the moment
    └── post.txt              3 title options + caption + hashtags
```

It was built for the GTA VI launch wave — every streamer's chat is erupting a dozen times a session right now — but it works for any game, any stream, any VOD where the chat log lines up with the recording.

## Why chat hype?

Clip detectors that watch the *video* guess. Your chat doesn't guess: when something incredible, hilarious or chaotic happens, chat erupts — message rate spikes far above baseline and fills with `W`, `GG`, `OMG`, `CLIP IT`, all-caps shouting and `!!!!`. ClipForge scores exactly those signals, finds the eruptions, and cuts around them (8 seconds before the peak by default, so the clip has its run-up).

## Design choices (the legit part)

- **Input files only.** ClipForge reads files on your disk. There is deliberately **no feature to download anyone's stream or VOD** — if it isn't your recording, this tool is not for it.
- **No posting, no uploading.** There is deliberately **no auto-posting feature**. You review every clip, edit the text so it sounds like you, and post it yourself, one platform at a time.
- **No view tricks, no spam tooling, no income promises.** ClipForge finds moments. What they earn is up to the content and the creator.
- **Use it only on your own recordings**, or on content you have explicit permission to clip. Clipping other creators' streams without permission is not a growth strategy, it's a takedown queue.

## Install

Requires Python 3.11+ and **ffmpeg** (with ffprobe) on your PATH:

```bash
# Ubuntu/Debian
sudo apt install ffmpeg
# macOS
brew install ffmpeg
# Windows
winget install Gyan.FFmpeg
```

Then:

```bash
git clone https://github.com/tahiryounas604/clipforge.git
cd clipforge
pip install .
```

Or run it without installing: `PYTHONPATH=src python3 -m clipforge ...`

## Quickstart

```bash
# 1. Just find the moments in a chat log
clipforge moments chat.jsonl --out moments.json

# 2. Cut vertical clips for those moments
clipforge cut vod.mp4 --moments moments.json --out-dir clips

# 3. Draft titles / captions / hashtags for those moments
clipforge hooks --moments moments.json --game "GTA VI"

# 4. Everything at once: VOD + chat log -> posting pack
clipforge pack vod.mp4 chat.jsonl --out my-pack

# 5. Live: tail a growing chat log while you stream, get alerted on spikes
clipforge watch live-chat.txt --duration 3600
```

### Chat log formats

Export the chat from your own VOD tooling (chat replay download, bot log, IRC log). Supported:

| Format | Shape |
|---|---|
| JSON Lines / JSON array | objects with `timestamp`/`time`/`offset`/`offset_seconds`, `author`/`user`/`name`, `text`/`message`/`comment` |
| CSV | header or bare `timestamp,author,text` rows |
| Plain text | `[12:34] user: message` or `[1:02:34] user: message` |

Timestamps can be seconds, `MM:SS`, or `H:MM:SS`. Malformed lines are skipped, never fatal. See `examples/` for samples.

### Useful options

- `--window 10` — spike detection window in seconds
- `--spike-factor 3.0` — how far above baseline a window must be to count
- `--length 30 --pre-roll 8` — clip length, and seconds before the peak to start
- `--mode crop` (default, full-bleed) or `--mode blurpad` (whole picture, blurred bands)
- `--game "Valorant"` + `--tags "#Valorant,#FPS"` — hooks default to a GTA VI set; override for any game

## How hype scoring works

Every message gets a transparent, inspectable score:

- **Keywords** — `clip it` (3.0), `clutch` (2.5), `pog`, `omg`, `lmao`, `no way`, `insane`, `gg`, `w`… each with a category (hype / clutch / funny / chaos) that later drives the title templates
- **Shouting** — ≥70% uppercase letters: +1.5
- **Exclamations** — +0.25 each, capped
- **Bursts** — repeated characters (`LOOOOL`, `WOOOO`): +0.75
- **Caps-token runs** — `W W W`, `GG GG`: +0.5

Scores are binned per second; a sliding window is a *moment* when its energy is at least `spike_factor`× the stream's own baseline (median per-second energy) with a minimum message count. The reported 0–100 score is relative to that stream — a 90 on a quiet stream and a 90 on a huge stream are both "chat lost it, *for this chat*".

## Honest limits

- **Your chat log must come from your own tooling**, and its timestamps must line up with the VOD's timeline. A chat log from a different session produces confident nonsense.
- **Detection is a heuristic.** Loud chat usually means a great moment — but raids, arguments, bot spam and giveaway spam are loud too. Watch every clip before posting (the checklist in every pack says so).
- **Hooks are templates, not an AI and not a promise.** They are starting points built from what chat actually said. Edit them. Nothing here guarantees views, followers, or income.
- **Cutting re-encodes.** Cuts are frame-accurate, which means a real libx264 encode per clip — a long moment list takes real CPU time.
- **Live `watch` mode reads appended lines** in the plain-text or JSONL shapes; it does not connect to any platform's chat API.

## Tests

```bash
python -m pytest -q
```

36 tests: chat parsers (all formats + malformed input), hype scoring, spike detection (quiet chat → zero moments; planted eruption → the right window), hooks, the watcher, and real-ffmpeg integration (synthetic video → verified 1080×1920 h264 clip → full pack structure).

## License

GPL-3.0 — see [LICENSE](LICENSE).

## Author

Tahir Younas — Tytechlabs — https://www.linkedin.com/in/tahiryounas604
