"""ffmpeg cutting: vertical reframe, clip extraction, thumbnails.

The reframe follows the proven approach from the sibling
``clipmachine`` product — scale-to-cover + centre crop for a
full-bleed 9:16 frame — plus a ``blurpad`` mode that keeps the
whole picture: the source is scaled to fit and the empty bands are
filled with a blurred, darkened copy of itself. Code here is
fresh; the filter-graph idea is the shared one.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

TARGET = (1080, 1920)

INSTALL_HINT = (
    "ffmpeg is required but was not found on PATH.\n"
    "Install it, then re-run:\n"
    "  Ubuntu/Debian:  sudo apt install ffmpeg\n"
    "  macOS:          brew install ffmpeg\n"
    "  Windows:        winget install Gyan.FFmpeg"
)


def require_ffmpeg() -> str:
    """Return the ffmpeg path, or raise with install instructions."""
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError(INSTALL_HINT)
    return path


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip()[-1500:]
        raise RuntimeError(
            f"command failed (exit {proc.returncode}): {' '.join(cmd[:3])} …\n{tail}"
        )


def probe(path: str) -> dict:
    """ffprobe facts: width, height, duration, video codec, has_audio."""
    if not shutil.which("ffprobe"):
        raise RuntimeError(INSTALL_HINT)
    proc = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", path],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path}: {(proc.stderr or '')[-500:]}")
    data = json.loads(proc.stdout)
    video = next((s for s in data.get("streams", [])
                  if s.get("codec_type") == "video"), {})
    return {
        "width": video.get("width"),
        "height": video.get("height"),
        "codec": video.get("codec_name"),
        "duration": float(data.get("format", {}).get("duration", 0.0)),
        "has_audio": any(s.get("codec_type") == "audio"
                         for s in data.get("streams", [])),
    }


def reframe_filter(width: int = TARGET[0], height: int = TARGET[1],
                   mode: str = "crop") -> str:
    """Video filter chain turning any input into width x height."""
    if mode == "crop":
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1"
        )
    if mode == "blurpad":
        return (
            "split[a][b];"
            f"[a]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},gblur=sigma=24,eq=brightness=-0.15[bg];"
            f"[b]scale={width}:{height}:force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1"
        )
    raise ValueError(f"unknown reframe mode: {mode!r} (use 'crop' or 'blurpad')")


def cut_clip(source: str, start: float, duration: float, output_path: str,
             mode: str = "crop") -> dict:
    """Cut *duration* seconds from *start* into a vertical MP4.

    Input-side seeking + re-encode, so cuts are frame-accurate.
    Returns the ffprobe facts of the produced file.
    """
    require_ffmpeg()
    if not os.path.isfile(source):
        raise FileNotFoundError(f"source video not found: {source}")
    if duration <= 0:
        raise ValueError("duration must be positive")
    start = max(0.0, start)
    has_audio = probe(source)["has_audio"]
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}", "-i", source,
        "-t", f"{duration:.3f}",
        "-vf", reframe_filter(mode=mode),
    ]
    cmd += ["-c:a", "aac", "-b:a", "128k"] if has_audio else ["-an"]
    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", output_path,
    ]
    _run(cmd)
    return {"path": output_path, **probe(output_path)}


def grab_thumbnail(source: str, at: float, output_path: str) -> dict:
    """Extract one frame at *at* seconds as a JPEG thumbnail."""
    require_ffmpeg()
    if not os.path.isfile(source):
        raise FileNotFoundError(f"source video not found: {source}")
    _run([
        "ffmpeg", "-y", "-ss", f"{max(0.0, at):.3f}", "-i", source,
        "-frames:v", "1", "-q:v", "3", output_path,
    ])
    return {"path": output_path, **probe(output_path)}
