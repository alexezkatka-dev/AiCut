import json
import shutil
import subprocess

import numpy as np
import pytest

from autoedit.build_preview import build_preview
from autoedit.config import load_profile
from autoedit.plan import EditPlan
from tests.make_samples import make_clip, make_tone

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")

W, H, FPS = 320, 180, 30


def _frames(path):
    """All frames as an (n, H, W, 3) uint8 array."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)


def _colour(frame):
    r, g, b = frame[60:120, 100:220].reshape(-1, 3).mean(axis=0)
    if max(r, g, b) < 40:
        return "black"
    return "red" if r > max(g, b) else "blue" if b > max(r, g) else "other"


@pytest.fixture
def plan_path(tmp_path):
    make_clip(tmp_path / "red.mp4", 6, color="red", size=(640, 360))
    make_clip(tmp_path / "blue.MOV", 6, color="blue", size=(640, 360), tone=300)
    make_tone(tmp_path / "vo.mp3", 6)
    plan = {
        "version": 1,
        "project": {"name": "t", "width": 1920, "height": 1080, "fps": FPS},
        # Cuts at 1.37 s (frame 41.1 -> 41) and a gap 2.37..2.5 s (frames 71..75).
        "video": [
            {"slot_id": "A", "source": "red.mp4", "src_in": 1.0, "src_out": 2.37, "start": 0.0, "duration": 1.37,
             "zoom_from": 1.0, "zoom_to": 1.2},
            {"slot_id": "B", "source": "blue.MOV", "src_in": 0.5, "src_out": 2.5, "start": 1.37, "duration": 1.0,
             "speed": 2.0, "volume": 0.5},
            {"slot_id": "C", "source": "red.mp4", "src_in": 3.0, "src_out": 4.0, "start": 2.5, "duration": 1.0},
        ],
        "audio": [{"kind": "voiceover", "source": "vo.mp3", "start": 0.0, "duration": 3.8, "volume": 1.0}],
        "text": [{"content": "100% ПРОВЕРКА", "start": 0.2, "duration": 1.0, "style": "accent"}],
    }
    path = tmp_path / "edit_plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return path


def test_cuts_land_on_planned_frames(plan_path):
    plan = EditPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    out = plan_path.parent / "out" / "preview.mp4"
    assert build_preview(plan, plan_path, out, load_profile("food_long"), height=H) == []

    frames = _frames(out)
    assert len(frames) == round(3.8 * FPS)  # audio is the longest item
    colours = [_colour(f) for f in frames]
    assert set(colours[:41]) == {"red"}
    assert set(colours[41:71]) == {"blue"}
    assert set(colours[71:75]) == {"black"}
    assert set(colours[75:105]) == {"red"}
    assert set(colours[105:]) == {"black"}


def test_preview_has_audio(plan_path):
    plan = EditPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    out = plan_path.parent / "preview.mp4"
    build_preview(plan, plan_path, out, load_profile("food_long"), height=H)
    streams = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0",
                              str(out)], capture_output=True, text=True, check=True).stdout.split()
    assert streams == ["video", "audio"]
