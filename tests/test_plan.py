import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from autoedit.plan import EditPlan, load_plan, missing_sources

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "edit_plan.example.json"


def _example() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_example_plan_loads():
    plan = load_plan(EXAMPLE)
    assert [v.slot_id for v in plan.video] == ["K01", "K02"]
    assert plan.total_duration == pytest.approx(6.94)
    assert plan.video[0].volume == 0.0  # clip sound muted by default


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d["video"][0].update(src_out=12.0), "src_out must be greater"),
    (lambda d: d["video"][1].update(start=2.0), "before the previous clip ends"),
    (lambda d: d["video"][0].update(duration=3.5), "but duration"),
    (lambda d: d["video"][0].update(zoom=1.2), "Extra inputs"),
    (lambda d: d["project"].update(name="курица 10"), "pattern"),
    (lambda d: d.update(version=2), "version"),
    (lambda d: d["audio"][0].update(kind="voice"), "kind"),
])
def test_bad_plans_are_rejected(mutate, message):
    data = _example()
    mutate(data)
    with pytest.raises(ValidationError, match=message):
        EditPlan.model_validate(data)


def test_speed_counts_towards_duration():
    data = _example()
    data["video"][0].update(src_in=10.0, src_out=15.68, speed=2.0)  # 5.68 s of source -> 2.84 s
    EditPlan.model_validate(data)


def test_missing_sources_resolved_next_to_plan(tmp_path):
    plan_path = tmp_path / "edit_plan.json"
    (tmp_path / "vo.mp3").write_bytes(b"x")
    missing = missing_sources(load_plan(EXAMPLE), plan_path)
    assert tmp_path / "vo.mp3" not in missing
    assert tmp_path / "footage" / "IMG_4821.MOV" in missing
    assert len(missing) == 3  # two clips + music
