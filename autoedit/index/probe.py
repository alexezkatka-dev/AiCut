"""ffprobe metadata and a cheap content hash for cache checks."""

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MediaInfo:
    duration: float
    fps: float
    width: int  # as displayed, i.e. after rotation
    height: int
    rotation: int  # degrees, as stored by the phone
    created: str | None


def _exe(name: str) -> str:
    exe = shutil.which(name)
    if exe is None:
        raise FileNotFoundError(f"{name} not found on PATH")
    return exe


def _rate(text: str) -> float:
    num, _, den = text.partition("/")
    return float(num) / float(den) if den and float(den) else float(num or 0)


def probe(path: Path) -> MediaInfo:
    out = subprocess.run([_exe("ffprobe"), "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
                          str(path)], capture_output=True, text=True, encoding="utf-8", check=True).stdout
    data = json.loads(out)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError(f"{path.name}: no video stream")
    rotation = int(float(video.get("tags", {}).get("rotate", 0)))
    for side in video.get("side_data_list", []):
        if "rotation" in side:
            rotation = int(side["rotation"])
    w, h = int(video["width"]), int(video["height"])
    if abs(rotation) % 180 == 90:
        w, h = h, w
    fmt = data.get("format", {})
    tags = fmt.get("tags", {})
    created = tags.get("com.apple.quicktime.creationdate") or tags.get("creation_time")
    duration = float(fmt.get("duration") or video.get("duration") or 0)
    return MediaInfo(duration, _rate(video.get("avg_frame_rate", "0/1")), w, h, rotation, created)


def file_hash(path: Path) -> str:
    """Size + mtime + first 1 MB: changes whenever the file is replaced or edited."""
    st = path.stat()
    with path.open("rb") as f:
        head = hashlib.sha1(f.read(1 << 20)).hexdigest()
    return f"{st.st_size}-{st.st_mtime_ns}-{head}"
