"""media_index.db (SQLite): files, sampled frames with embeddings, active takes (SPEC §3.4)."""

import sqlite3
from pathlib import Path

import numpy as np

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, hash TEXT NOT NULL, model TEXT NOT NULL,
    duration REAL, fps REAL, width INTEGER, height INTEGER, rotation INTEGER, created TEXT);
CREATE TABLE IF NOT EXISTS samples (
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE, t REAL NOT NULL, embedding BLOB NOT NULL,
    sharpness REAL, brightness REAL, motion REAL);
CREATE TABLE IF NOT EXISTS takes (
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE, start REAL NOT NULL, end REAL NOT NULL);
CREATE INDEX IF NOT EXISTS samples_file ON samples(file_id);
CREATE INDEX IF NOT EXISTS takes_file ON takes(file_id);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def files(conn: sqlite3.Connection) -> dict[str, tuple[int, str, str]]:
    """path -> (id, hash, model)."""
    return {p: (i, h, m) for i, p, h, m in conn.execute("SELECT id, path, hash, model FROM files")}


def delete_file(conn: sqlite3.Connection, file_id: int) -> None:
    conn.execute("DELETE FROM files WHERE id = ?", (file_id,))


def add_file(conn: sqlite3.Connection, path: str, file_hash: str, model: str, info, samples, takes) -> None:
    """samples: (t, embedding, sharpness, brightness, motion); takes: (start, end). One transaction per file."""
    with conn:
        conn.execute("DELETE FROM files WHERE path = ?", (path,))
        cur = conn.execute(
            "INSERT INTO files (path, hash, model, duration, fps, width, height, rotation, created) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (path, file_hash, model, info.duration, info.fps, info.width, info.height, info.rotation, info.created))
        fid = cur.lastrowid
        conn.executemany("INSERT INTO samples VALUES (?, ?, ?, ?, ?, ?)",
                         [(fid, t, np.asarray(e, np.float16).tobytes(), s, b, m) for t, e, s, b, m in samples])
        conn.executemany("INSERT INTO takes VALUES (?, ?, ?)", [(fid, s, e) for s, e in takes])


def load_samples(conn: sqlite3.Connection) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(file_ids, times, embeddings as float32 rows)."""
    rows = conn.execute("SELECT file_id, t, embedding FROM samples ORDER BY file_id, t").fetchall()
    if not rows:
        return np.zeros(0, int), np.zeros(0), np.zeros((0, 0), np.float32)
    ids = np.array([r[0] for r in rows])
    times = np.array([r[1] for r in rows])
    emb = np.stack([np.frombuffer(r[2], np.float16) for r in rows]).astype(np.float32)
    return ids, times, emb
