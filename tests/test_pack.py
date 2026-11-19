import json
import os
import shutil
import subprocess

import pytest

from clipforge.pack import build_pack
from tests.test_cutter import make_video

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None,
                                reason="ffmpeg not installed")


def _write_spiky_chatlog(path, video_seconds=20):
    """Plain-text chat log: calm, then an eruption inside a 20s VOD."""
    lines = []
    for t in range(0, 20, 2):
        lines.append(f"[0:{t:02d}] viewer{t}: nice stream")
    burst = ["OMG", "CLIP IT", "NO WAY!!!", "W W W", "INSANE", "POG",
             "GG GG", "LETS GOOO", "CLIP IT NOW", "WOW!!!", "CRAZY",
             "OMG OMG", "POGGERS", "CLIP THAT", "FIRE"]
    for i, text in enumerate(burst):
        lines.append(f"[0:10] fan{i}: {text}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_pack_structure(tmp_path):
    video = make_video(tmp_path / "vod.mp4", seconds=20)
    chat = tmp_path / "chat.txt"
    _write_spiky_chatlog(chat)
    out = tmp_path / "pack"
    summary = build_pack(video, str(chat), str(out),
                         min_window_messages=5, clip_length=6.0,
                         pre_roll=3.0)
    assert summary["moments_found"] >= 1
    entry = summary["clips"][0]
    folder = out / entry["folder"]
    assert (folder / "clip.mp4").is_file()
    assert (folder / "thumb.jpg").is_file()
    post = (folder / "post.txt").read_text(encoding="utf-8")
    assert "#GTAVI" in post
    assert (entry["clip"]["width"], entry["clip"]["height"]) == (1080, 1920)
    pack_json = json.loads((out / "pack.json").read_text(encoding="utf-8"))
    assert pack_json["moments_found"] == summary["moments_found"]
    checklist = (out / "POSTING-CHECKLIST.md").read_text(encoding="utf-8")
    assert "my own recording" in checklist


def test_pack_no_moments_still_writes_summary(tmp_path):
    video = make_video(tmp_path / "vod.mp4", seconds=20)
    chat = tmp_path / "chat.txt"
    chat.write_text("[0:01] a: hello\n[0:05] b: nice\n", encoding="utf-8")
    out = tmp_path / "pack"
    summary = build_pack(video, str(chat), str(out))
    assert summary["moments_found"] == 0
    assert (out / "pack.json").is_file()
    assert (out / "POSTING-CHECKLIST.md").is_file()
