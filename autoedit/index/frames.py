"""Decodes sample frames with FFmpeg into memory and measures simple image qualities."""

import subprocess
from collections.abc import Iterator
from pathlib import Path

import numpy as np

from autoedit.index.probe import MediaInfo, _exe


def sample_size(info: MediaInfo, width: int) -> tuple[int, int]:
    return width, max(2, round(width * info.height / info.width / 2) * 2)


def iter_frames(path: Path, info: MediaInfo, every: float, width: int) -> Iterator[tuple[float, np.ndarray]]:
    """(time, RGB frame) every `every` seconds, already rotated as displayed."""
    w, h = sample_size(info, width)
    # -hwaccel auto uses the GPU decoder when there is one (phone HEVC is slow on CPU) and falls back silently.
    cmd = [_exe("ffmpeg"), "-v", "error", "-hwaccel", "auto", "-i", str(path), "-an",
           "-vf", f"fps=1/{every},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    size = w * h * 3
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        i = 0
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            yield i * every, np.frombuffer(buf, np.uint8).reshape(h, w, 3)
            i += 1
        err = proc.stderr.read().decode("utf-8", "replace")
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed on {path.name}: {err.strip()}")


def gray(rgb: np.ndarray) -> np.ndarray:
    return rgb.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32) / 255


def sharpness(g: np.ndarray) -> float:
    """Variance of the Laplacian: higher is sharper."""
    lap = -4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
    return float(lap.var())


def brightness(g: np.ndarray) -> float:
    return float(g.mean())


def motion(g: np.ndarray, prev: np.ndarray | None) -> float:
    """Mean absolute change since the previous sample, 0..1."""
    return 0.0 if prev is None else float(np.abs(g - prev).mean())
