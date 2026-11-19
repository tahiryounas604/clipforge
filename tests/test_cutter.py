import shutil
import subprocess

import pytest

from clipforge import cutter

HAS_FFMPEG = shutil.which("ffmpeg") is not None
pytestmark = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")


def make_video(path, seconds=20, size="640x360"):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"testsrc=duration={seconds}:size={size}:rate=30",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", str(path)],
        capture_output=True, check=True,
    )
    return str(path)


def test_missing_ffmpeg_error_explains_install(monkeypatch):
    monkeypatch.setattr(cutter.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError) as excinfo:
        cutter.require_ffmpeg()
    assert "apt install ffmpeg" in str(excinfo.value)


def test_reframe_filters():
    assert "crop=1080:1920" in cutter.reframe_filter(mode="crop")
    blur = cutter.reframe_filter(mode="blurpad")
    assert "gblur" in blur and "overlay" in blur
    with pytest.raises(ValueError):
        cutter.reframe_filter(mode="stretch")


def test_cut_produces_1080x1920_h264(tmp_path):
    src = make_video(tmp_path / "vod.mp4", seconds=20)
    out = str(tmp_path / "clip.mp4")
    info = cutter.cut_clip(src, start=5.0, duration=5.0, output_path=out)
    assert info["width"] == 1080
    assert info["height"] == 1920
    assert info["codec"] == "h264"
    assert 4.5 <= info["duration"] <= 5.6


def test_cut_blurpad_mode(tmp_path):
    src = make_video(tmp_path / "vod.mp4", seconds=12)
    info = cutter.cut_clip(src, start=2.0, duration=3.0,
                           output_path=str(tmp_path / "clip.mp4"),
                           mode="blurpad")
    assert (info["width"], info["height"]) == (1080, 1920)


def test_thumbnail_is_jpeg_frame(tmp_path):
    src = make_video(tmp_path / "vod.mp4", seconds=12)
    out = str(tmp_path / "thumb.jpg")
    info = cutter.grab_thumbnail(src, at=6.0, output_path=out)
    assert info["codec"] == "mjpeg"
    assert info["width"] == 640


def test_cut_rejects_missing_source(tmp_path):
    with pytest.raises(FileNotFoundError):
        cutter.cut_clip(str(tmp_path / "nope.mp4"), 0.0, 5.0,
                        str(tmp_path / "x.mp4"))
