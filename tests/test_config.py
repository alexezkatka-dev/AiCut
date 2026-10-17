from pathlib import Path

from autoedit.config import ROOT, load_config, load_profile


def test_config_created_from_example(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    path = tmp_path / "config.yaml"
    cfg = load_config(path)
    assert path.is_file()
    assert cfg.drafts_dir() == tmp_path / "Local" / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"
    assert cfg.work_dir() == ROOT / "work"
    assert cfg.preview.height == 540


def test_explicit_drafts_dir(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text('capcut:\n  drafts_dir: "D:/Мои черновики"\n', encoding="utf-8")
    assert load_config(path).drafts_dir() == Path("D:/Мои черновики")


def test_food_long_text_styles():
    styles = load_profile("food_long").text_styles
    assert styles["accent"].color == "#FFD400"
    assert styles["bold"].stroke_width == 40
