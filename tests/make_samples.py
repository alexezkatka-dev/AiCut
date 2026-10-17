"""Synthetic media for tests and the stage 0 check, generated with FFmpeg lavfi sources.

Run: python -m tests.make_samples OUT_DIR
"""

import shutil
import subprocess
import sys
from pathlib import Path

WIDTH, HEIGHT, FPS = 1920, 1080, 30

# The on-screen counter shows tenths of a second (25 = 2.5 s), so trims are visible.
_CLIP = "testsrc=size={w}x{h}:rate={fps}:duration={sec}:decimals=1"
VIDEO_PATTERNS = {
    "clip1": _CLIP,
    "clip2": _CLIP + ",hue=h=120:s=0.4",  # same pattern, different colours
}


def ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe is None:
        raise FileNotFoundError("ffmpeg not found on PATH")
    return exe


def _ffmpeg(args: list[str]) -> None:
    subprocess.run([ffmpeg_exe(), "-v", "error", "-y", *args], check=True)


def make_samples(out_dir: Path, clip_sec: float = 8.0, vo_sec: float = 6.5) -> dict[str, Path]:
    """Write clip1.mp4, clip2.mp4 (test pattern) and vo.mp3 (sine tone); return paths by key."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for key, pattern in VIDEO_PATTERNS.items():
        path = out_dir / f"{key}.mp4"
        src = pattern.format(w=WIDTH, h=HEIGHT, fps=FPS, sec=clip_sec)
        _ffmpeg(["-f", "lavfi", "-i", src, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)])
        paths[key] = path
    vo = out_dir / "vo.mp3"
    _ffmpeg(["-f", "lavfi", "-i", f"sine=frequency=440:duration={vo_sec}", "-c:a", "libmp3lame", str(vo)])
    paths["vo"] = vo
    return paths


if __name__ == "__main__":
    for key, path in make_samples(Path(sys.argv[1])).items():
        print(key, path)
