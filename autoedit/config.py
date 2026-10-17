"""Settings from config.yaml and edit-style profiles from profiles/<name>.yaml."""

import os
import shutil
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"
CONFIG_EXAMPLE = ROOT / "config.example.yaml"
PROFILES_DIR = ROOT / "profiles"


class _Section(BaseModel):
    # Sections for later stages (models, index, matcher) are read when those stages need them.
    model_config = ConfigDict(extra="ignore")


class CapCutCfg(_Section):
    drafts_dir: str = ""  # empty = standard CapCut folder
    draft_prefix: str = "AE_"


class PathsCfg(_Section):
    work_dir: str = "work"


class PreviewCfg(_Section):
    height: int = Field(540, gt=0)


class Config(_Section):
    capcut: CapCutCfg = Field(default_factory=CapCutCfg)
    paths: PathsCfg = Field(default_factory=PathsCfg)
    preview: PreviewCfg = Field(default_factory=PreviewCfg)
    profile: str = "food_long"

    def drafts_dir(self) -> Path | None:
        if self.capcut.drafts_dir:
            return Path(self.capcut.drafts_dir)
        return default_drafts_dir()

    def work_dir(self) -> Path:
        path = Path(self.paths.work_dir)
        return path if path.is_absolute() else ROOT / path


def default_drafts_dir() -> Path | None:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    return Path(local) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"


def load_config(path: Path = CONFIG_PATH) -> Config:
    """Read config.yaml; on first run create it from config.example.yaml."""
    if not path.exists():
        shutil.copyfile(CONFIG_EXAMPLE, path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Config.model_validate(data)


class TextStyleCfg(_Section):
    color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    stroke_width: float = Field(40.0, ge=0, le=100)  # CapCut units
    size: float = Field(9.0, gt=0)  # CapCut font size
    bold: bool = True
    position_y: float = -0.55  # half frame heights from centre, up is +


class Profile(_Section):
    text_styles: dict[str, TextStyleCfg] = Field(default_factory=dict)


def load_profile(name: str, profiles_dir: Path = PROFILES_DIR) -> Profile:
    path = profiles_dir / f"{name}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Profile.model_validate(data)
