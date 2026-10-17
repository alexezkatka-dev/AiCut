"""Synthetic media for tests and stage checks, generated with FFmpeg lavfi sources.

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


def make_clip(path: Path, sec: float, *, hue: int = 0, color: str | None = None,
              size: tuple[int, int] = (WIDTH, HEIGHT), fps: int = FPS, tone: int | None = None) -> Path:
    """Test-pattern clip with a tenths-of-a-second counter, or a solid colour; optional sine sound."""
    path.parent.mkdir(parents=True, exist_ok=True)
    w, h = size
    if color:
        src = f"color=c={color}:s={w}x{h}:r={fps}:d={sec}"
    else:
        src = _CLIP.format(w=w, h=h, fps=fps, sec=sec) + (f",hue=h={hue}:s=0.5" if hue else "")
    args = ["-f", "lavfi", "-i", src]
    if tone:
        args += ["-f", "lavfi", "-i", f"sine=frequency={tone}:duration={sec}", "-c:a", "aac"]
    fmt = ["-f", "mov"] if path.suffix.lower() == ".mov" else []
    _ffmpeg([*args, "-c:v", "libx264", "-pix_fmt", "yuv420p", *fmt, str(path)])
    return path


def make_tone(path: Path, sec: float, freq: int = 440) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg(["-f", "lavfi", "-i", f"sine=frequency={freq}:duration={sec}", "-c:a", "libmp3lame", str(path)])
    return path


def make_samples(out_dir: Path, clip_sec: float = 8.0, vo_sec: float = 6.5) -> dict[str, Path]:
    """Stage 0 set: clip1.mp4, clip2.mp4 (test pattern) and vo.mp3 (sine tone); paths by key."""
    paths = {"clip1": make_clip(out_dir / "clip1.mp4", clip_sec),
             "clip2": make_clip(out_dir / "clip2.mp4", clip_sec, hue=120)}
    paths["vo"] = make_tone(out_dir / "vo.mp3", vo_sec)
    return paths


# Stand-ins for the sources named in examples/edit_plan.example.json (stage 1 check).
EXAMPLE_MEDIA = {
    "footage/IMG_4821.MOV": dict(sec=17.0),
    "footage/IMG_4825.MOV": dict(sec=10.0, hue=120),
    "vo.mp3": dict(sec=7.5, freq=440),
    "music/kitchen_light.mp3": dict(sec=7.5, freq=220),
}


def make_example_media(project_dir: Path) -> None:
    for rel, opts in EXAMPLE_MEDIA.items():
        path = project_dir / rel
        if rel.endswith(".mp3"):
            make_tone(path, opts["sec"], opts["freq"])
        else:
            make_clip(path, opts["sec"], hue=opts.get("hue", 0))


if __name__ == "__main__":
    for key, path in make_samples(Path(sys.argv[1])).items():
        print(key, path)
