"""Indexes a footage folder into media_index.db (SPEC §5.1). Unchanged files are skipped without loading the model."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from autoedit.index import db
from autoedit.index.frames import brightness, gray, iter_frames, motion, sharpness
from autoedit.index.probe import file_hash, probe
from autoedit.index.takes import find_takes

VIDEO_EXT = {".mov", ".mp4", ".m4v", ".mkv", ".avi"}
BATCH = 32


@dataclass
class IndexSettings:
    model: str
    pretrained: str
    every: float
    width: int
    motion_min: float
    shake: float

    @property
    def cache_key(self) -> str:
        """Changing any of these re-indexes every file."""
        return f"{self.model}/{self.pretrained}/{self.every}/{self.width}"


@dataclass
class IndexStats:
    indexed: int = 0
    skipped: int = 0
    removed: int = 0


def list_videos(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXT)


def index_folder(folder: Path, db_path: Path, s: IndexSettings, make_embedder: Callable[[], object],
                 log: Callable[[str], None] = print) -> IndexStats:
    stats = IndexStats()
    conn = db.connect(db_path)
    try:
        known = db.files(conn)
        videos = list_videos(folder)
        present = {p.resolve().as_posix() for p in videos}
        for path, (fid, _, _) in known.items():
            if path not in present:
                with conn:
                    db.delete_file(conn, fid)
                stats.removed += 1

        todo = []
        for p in videos:
            key = p.resolve().as_posix()
            h = file_hash(p)
            if key in known and known[key][1:] == (h, s.cache_key):
                stats.skipped += 1
            else:
                todo.append((p, key, h))

        embedder = make_embedder() if todo else None
        for n, (p, key, h) in enumerate(todo, 1):
            info = probe(p)
            samples = _sample_file(p, info, s, embedder)
            takes = find_takes([m for *_, m in samples], s.every, info.duration, s.motion_min, s.shake)
            db.add_file(conn, key, h, s.cache_key, info, samples, takes)
            log(f"[{n}/{len(todo)}] {p.name}: {info.duration:.1f} с, кадров {len(samples)}, рабочих участков {len(takes)}")
            stats.indexed += 1
    finally:
        conn.close()
    return stats


def _sample_file(path: Path, info, s: IndexSettings, embedder) -> list[tuple]:
    rows, batch, prev = [], [], None
    for t, rgb in iter_frames(path, info, s.every, s.width):
        g = gray(rgb)
        rows.append([t, None, sharpness(g), brightness(g), motion(g, prev)])
        batch.append(rgb)
        prev = g
        if len(batch) == BATCH:
            _embed(rows, batch, embedder)
    if batch:
        _embed(rows, batch, embedder)
    if len(rows) > 1:
        rows[0][4] = rows[1][4]  # the first sample has no predecessor
    return [tuple(r) for r in rows]


def _embed(rows: list[list], batch: list, embedder) -> None:
    for row, e in zip(rows[len(rows) - len(batch):], embedder.images(batch)):
        row[1] = e
    batch.clear()
