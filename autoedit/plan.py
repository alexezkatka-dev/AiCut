"""edit_plan.json: the single contract between planners and builders (SPEC §3.3). Times are seconds."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")  # a typo in a hand-written plan is an error, not a no-op


class Alternative(_Model):
    source: str
    src_in: float = Field(ge=0)
    score: float


class VideoItem(_Model):
    slot_id: str
    role: str = "step"
    source: str
    src_in: float = Field(ge=0)
    src_out: float
    start: float = Field(ge=0)
    duration: float = Field(gt=0)
    speed: float = Field(1.0, gt=0)
    zoom_from: float = Field(1.0, gt=0)
    zoom_to: float = Field(1.0, gt=0)
    volume: float = Field(0.0, ge=0)  # clip's own sound; muted by default under a voiceover
    confidence: float = Field(1.0, ge=0, le=1)
    needs_review: bool = False
    alternatives: list[Alternative] = []

    @model_validator(mode="after")
    def _source_range(self):
        if self.src_out <= self.src_in:
            raise ValueError(f"{self.slot_id}: src_out must be greater than src_in")
        return self

    @property
    def src_duration(self) -> float:
        return self.src_out - self.src_in

    @property
    def end(self) -> float:
        return self.start + self.duration


class AudioItem(_Model):
    kind: Literal["voiceover", "music", "sfx"]
    source: str
    src_in: float = Field(0.0, ge=0)
    start: float = Field(ge=0)
    duration: float = Field(gt=0)
    volume: float = Field(1.0, ge=0)

    @property
    def end(self) -> float:
        return self.start + self.duration


class TextItem(_Model):
    content: str = Field(min_length=1)
    start: float = Field(ge=0)
    duration: float = Field(gt=0)
    style: str = "bold"

    @property
    def end(self) -> float:
        return self.start + self.duration


class Project(_Model):
    name: str = Field(pattern=r"^[A-Za-z0-9_-]+$")  # becomes part of the draft folder name
    width: int = Field(1920, gt=0)
    height: int = Field(1080, gt=0)
    fps: int = Field(30, gt=0)
    profile: str = "food_long"


class EditPlan(_Model):
    version: Literal[1]
    project: Project
    video: list[VideoItem] = Field(min_length=1)
    audio: list[AudioItem] = []
    text: list[TextItem] = []
    subtitles: str | None = None

    @model_validator(mode="after")
    def _timeline(self):
        tol = 0.5 / self.project.fps  # half a frame
        prev_end = 0.0
        for v in self.video:
            if v.start < prev_end - tol:
                raise ValueError(f"video {v.slot_id}: starts at {v.start}s, before the previous clip ends ({prev_end:.3f}s)")
            timeline_len = v.src_duration / v.speed
            if abs(timeline_len - v.duration) > tol:
                raise ValueError(f"video {v.slot_id}: (src_out - src_in) / speed = {timeline_len:.3f}s, "
                                 f"but duration = {v.duration}s")
            prev_end = v.end
        return self

    @property
    def total_duration(self) -> float:
        return max(item.end for item in [*self.video, *self.audio, *self.text])


def load_plan(path: Path) -> EditPlan:
    return EditPlan.model_validate_json(path.read_text(encoding="utf-8"))


def resolve_source(plan_path: Path, source: str) -> Path:
    """Sources are relative to the folder of edit_plan.json unless absolute."""
    path = Path(source)
    return path if path.is_absolute() else plan_path.parent / path


def missing_sources(plan: EditPlan, plan_path: Path) -> list[Path]:
    sources = [v.source for v in plan.video] + [a.source for a in plan.audio]
    paths = dict.fromkeys(resolve_source(plan_path, s) for s in sources)  # ordered, unique
    return [p for p in paths if not p.is_file()]
