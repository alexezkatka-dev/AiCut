import json
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from autoedit.build_capcut import build_draft
from autoedit.config import load_profile
from autoedit.plan import EditPlan, load_plan
from tests.make_samples import make_example_media

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "edit_plan.example.json"
NOW = datetime(2026, 10, 17, 15, 30)
US = 1_000_000


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    d = tmp_path_factory.mktemp("example")
    make_example_media(d)
    shutil.copyfile(EXAMPLE, d / "edit_plan.json")
    return d / "edit_plan.json"


def _tracks(draft):
    content = json.loads((draft / "draft_content.json").read_text(encoding="utf-8"))
    return content, {t["name"]: t["segments"] for t in content["tracks"]}


def test_example_plan_to_draft(project, tmp_path):
    plan = load_plan(project)
    draft = build_draft(plan, project, tmp_path, load_profile("food_long"), NOW)
    assert draft.name == "AE_20261017-1530_chicken_10min"

    content, tracks = _tracks(draft)
    assert list(tracks) == ["video_main", "audio_vo", "audio_music", "text_overlay"]
    assert content["duration"] == round(6.94 * US)

    video = tracks["video_main"]
    assert [s["target_timerange"] for s in video] == [
        {"start": 0, "duration": round(2.84 * US)},
        {"start": round(2.84 * US), "duration": round(4.10 * US)},
    ]
    assert [s["source_timerange"]["start"] for s in video] == [round(12.40 * US), round(4.00 * US)]
    assert [s["volume"] for s in video] == [0.0, 0.0]
    zooms = [[kf["values"][0] for kf in s["common_keyframes"][0]["keyframe_list"]] for s in video]
    assert zooms == [[1.0, 1.12], [1.0, 1.06]]

    assert tracks["audio_vo"][0]["volume"] == 1.0
    assert tracks["audio_music"][0]["volume"] == 0.12
    assert tracks["audio_music"][0]["target_timerange"] == {"start": 0, "duration": round(6.94 * US)}

    (title,) = tracks["text_overlay"]
    assert title["target_timerange"] == {"start": round(0.2 * US), "duration": round(2.4 * US)}
    assert title["clip"]["transform"]["y"] == -0.55
    text = json.loads(content["materials"]["texts"][0]["content"])
    assert text["text"] == "DRY AGAIN?"
    assert text["styles"][0]["strokes"][0]["width"] > 0


def test_speed_and_static_zoom(project, tmp_path):
    data = json.loads(project.read_text(encoding="utf-8"))
    data["video"][0].update(src_in=8.0, src_out=13.68, speed=2.0, zoom_from=1.1, zoom_to=1.1)
    plan = EditPlan.model_validate(data)
    _, tracks = _tracks(build_draft(plan, project, tmp_path, load_profile("food_long"), NOW))
    seg = tracks["video_main"][0]
    assert seg["speed"] == 2.0
    assert seg["target_timerange"]["duration"] == round(2.84 * US)
    assert seg["common_keyframes"] == []
    assert seg["clip"]["scale"] == {"x": 1.1, "y": 1.1}


def test_too_short_source_leaves_no_draft(project, tmp_path):
    data = json.loads(project.read_text(encoding="utf-8"))
    data["video"][1].update(src_in=8.0, src_out=12.1)  # IMG_4825 is 10 s long
    plan = EditPlan.model_validate(data)
    with pytest.raises(ValueError, match="K02: IMG_4825.MOV is shorter"):
        build_draft(plan, project, tmp_path, load_profile("food_long"), NOW)
    assert list(tmp_path.iterdir()) == []


def test_unknown_text_style_leaves_no_draft(project, tmp_path):
    data = json.loads(project.read_text(encoding="utf-8"))
    data["text"][0]["style"] = "neon"
    with pytest.raises(ValueError, match="neon"):
        build_draft(EditPlan.model_validate(data), project, tmp_path, load_profile("food_long"), NOW)
    assert list(tmp_path.iterdir()) == []


def test_existing_draft_untouched(project, tmp_path):
    taken = tmp_path / "AE_20261017-1530_chicken_10min"
    taken.mkdir()
    (taken / "draft_content.json").write_text("users own", encoding="utf-8")
    draft = build_draft(load_plan(project), project, tmp_path, load_profile("food_long"), NOW)
    assert draft.name.endswith("_2")
    assert (taken / "draft_content.json").read_text(encoding="utf-8") == "users own"
