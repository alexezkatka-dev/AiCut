import shutil
import subprocess

import numpy as np
import pytest

from autoedit.index import db
from autoedit.index.indexer import IndexSettings, index_folder
from autoedit.index.probe import probe
from autoedit.index.takes import find_takes
from autoedit.search import search, write_report
from tests.make_samples import make_clip

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")

SETTINGS = IndexSettings("fake", "none", 0.5, 64, 0.01, 0.15)
COLOURS = {"red": [1, 0, 0], "green": [0, 1, 0], "blue": [0, 0, 1]}


class FakeEmbedder:
    """Mean colour as the 'embedding'; colour words as the 'text' side."""

    def images(self, frames):
        v = np.stack([f.reshape(-1, 3).mean(axis=0) for f in frames]).astype(np.float32)
        return v / np.linalg.norm(v, axis=1, keepdims=True)

    def text(self, query):
        v = np.array(COLOURS[query], np.float32)
        return v / np.linalg.norm(v)


def _never():
    raise AssertionError("model must not load when nothing changed")


@pytest.fixture
def footage(tmp_path):
    d = tmp_path / "footage"
    make_clip(d / "IMG_0001.MOV", 3, color="red", size=(320, 180))
    make_clip(d / "IMG_0002.mp4", 4, color="blue", size=(320, 180))
    make_clip(d / "IMG_0003.MOV", 5, size=(320, 180))  # moving test pattern
    (d / "notes.txt").write_text("not a video")
    return d


@needs_ffmpeg
def test_index_search_and_cache(footage, tmp_path):
    db_path = tmp_path / "work" / "media_index.db"
    stats = index_folder(footage, db_path, SETTINGS, FakeEmbedder, log=lambda _: None)
    assert (stats.indexed, stats.skipped, stats.removed) == (3, 0, 0)

    conn = db.connect(db_path)
    counts = dict(conn.execute("SELECT f.path, COUNT(*) FROM samples s JOIN files f ON f.id = s.file_id "
                               "GROUP BY f.path").fetchall())
    assert sorted(counts.values()) == [6, 8, 10]  # one sample per 0.5 s

    hits = search(conn, FakeEmbedder().text("blue"), top=2)
    assert hits[0].path.name == "IMG_0002.mp4"
    assert 0 <= hits[0].time < 4
    report = write_report("blue", hits, tmp_path / "work" / "search.html")
    assert "IMG_0002.mp4" in report.read_text(encoding="utf-8")
    assert (tmp_path / "work" / "thumbs" / "hit1.jpg").is_file()
    conn.close()

    # Second run: nothing changed, the model is never loaded.
    assert index_folder(footage, db_path, SETTINGS, _never, log=lambda _: None).skipped == 3

    # A replaced file is re-indexed, a deleted one is dropped.
    make_clip(footage / "IMG_0001.MOV", 2, color="green", size=(320, 180))
    (footage / "IMG_0003.MOV").unlink()
    stats = index_folder(footage, db_path, SETTINGS, FakeEmbedder, log=lambda _: None)
    assert (stats.indexed, stats.skipped, stats.removed) == (1, 1, 1)
    conn = db.connect(db_path)
    assert search(conn, FakeEmbedder().text("green"), top=1)[0].path.name == "IMG_0001.MOV"
    conn.close()


@needs_ffmpeg
def test_rotated_phone_clip(tmp_path):
    src = make_clip(tmp_path / "flat.mp4", 2, size=(320, 180))
    rotated = tmp_path / "rotated.MOV"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-display_rotation", "90", "-i", str(src), "-c", "copy",
                    str(rotated)], check=True)
    info = probe(rotated)
    assert abs(info.rotation) == 90
    assert (info.width, info.height) == (180, 320)
    assert info.duration == pytest.approx(2, abs=0.1)

    d = tmp_path / "f"
    d.mkdir()
    shutil.move(rotated, d / rotated.name)
    index_folder(d, tmp_path / "i.db", SETTINGS, FakeEmbedder, log=lambda _: None)  # frames decode as portrait


def test_takes_skip_still_and_shaky_edges():
    #          still      action          shake
    motion = [0.0] * 4 + [0.05] * 8 + [0.4] * 3
    assert find_takes(motion, 0.5, 7.5, 0.01, 0.15) == [(2.0, 6.0)]


def test_takes_merge_short_pauses_and_drop_blips():
    motion = [0.05] * 4 + [0.0] * 2 + [0.05] * 4 + [0.0] * 6 + [0.05] + [0.0] * 4
    takes = find_takes(motion, 0.5, 10.5, 0.01, 0.15)
    assert len(takes) == 1 and takes[0][0] == 0.0 and takes[0][1] >= 5.0


def test_still_clip_keeps_middle():
    assert find_takes([0.0] * 10, 0.5, 5.0, 0.01, 0.15) == [(0.5, 4.5)]
