import json
import shutil
from datetime import datetime

import pytest

from tests.make_samples import make_samples
from tools.stage0_smoke import CLIPS, TITLE, build_smoke_draft, inspect_user_drafts

US = 1_000_000
NOW = datetime(2026, 10, 17, 15, 30)
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    return make_samples(tmp_path_factory.mktemp("media"))


def _content(draft):
    return json.loads((draft / "draft_content.json").read_text(encoding="utf-8"))


@needs_ffmpeg
def test_smoke_draft_layout(tmp_path, media):
    draft = build_smoke_draft(tmp_path, media, NOW)
    assert draft.name == "AE_20261017-1530_smoke"
    assert (draft / "draft_meta_info.json").is_file()

    content = _content(draft)
    tracks = {t["name"]: t["segments"] for t in content["tracks"]}
    assert set(tracks) == {"video_main", "audio_vo", "text_overlay"}

    video = tracks["video_main"]
    durations = [round(dur * US) for _, _, dur, _ in CLIPS]
    assert [s["target_timerange"] for s in video] == [
        {"start": 0, "duration": durations[0]},
        {"start": durations[0], "duration": durations[1]},
    ]
    assert [s["source_timerange"]["start"] for s in video] == [round(c[1] * US) for c in CLIPS]
    zooms = [[kf["values"][0] for kf in s["common_keyframes"][0]["keyframe_list"]] for s in video]
    assert zooms == [[1.0, zoom_to] for *_, zoom_to in CLIPS]

    (vo,) = tracks["audio_vo"]
    assert vo["target_timerange"] == {"start": 0, "duration": sum(durations)}

    (title,) = tracks["text_overlay"]
    text, t_start, t_dur = TITLE
    assert title["target_timerange"] == {"start": round(t_start * US), "duration": round(t_dur * US)}
    assert json.loads(content["materials"]["texts"][0]["content"])["text"] == text


@needs_ffmpeg
def test_existing_draft_is_never_overwritten(tmp_path, media):
    taken = tmp_path / "AE_20261017-1530_smoke"
    taken.mkdir()
    (taken / "marker.txt").write_text("user data")

    draft = build_smoke_draft(tmp_path, media, NOW)

    assert draft.name == "AE_20261017-1530_smoke_2"
    assert (taken / "marker.txt").read_text() == "user data"
    assert sorted(p.name for p in taken.iterdir()) == ["marker.txt"]


def test_inspect_user_drafts_counts_plain_and_encrypted(tmp_path):
    (tmp_path / "Plain").mkdir()
    (tmp_path / "Plain" / "draft_content.json").write_text('{"tracks": []}', encoding="utf-8")
    (tmp_path / "Encrypted").mkdir()
    (tmp_path / "Encrypted" / "draft_content.json").write_bytes(b"\x8f\x02\xff\x10binary")
    (tmp_path / "AE_20261017-1530_smoke").mkdir()  # our own drafts are skipped
    (tmp_path / "AE_20261017-1530_smoke" / "draft_content.json").write_text("{}", encoding="utf-8")
    (tmp_path / "Empty").mkdir()

    assert inspect_user_drafts(tmp_path) == (1, 1)
