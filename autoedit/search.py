"""Text search over the media index: best-matching clips with the moment and a thumbnail report."""

import html
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from autoedit.index import db
from autoedit.index.probe import _exe


@dataclass
class Hit:
    path: Path
    time: float
    score: float
    take: tuple[float, float] | None  # active take containing `time`


def search(conn: sqlite3.Connection, query_vec: np.ndarray, top: int = 5) -> list[Hit]:
    """Rank files by their best-matching sample (max similarity over the clip's frames)."""
    ids, times, emb = db.load_samples(conn)
    if not len(ids):
        return []
    scores = emb @ query_vec.astype(np.float32)
    best: dict[int, int] = {}
    for i, fid in enumerate(ids):
        if fid not in best or scores[i] > scores[best[fid]]:
            best[fid] = i
    ranked = sorted(best.items(), key=lambda kv: -scores[kv[1]])[:top]
    paths = {fid: p for fid, p in conn.execute("SELECT id, path FROM files")}
    hits = []
    for fid, i in ranked:
        t = float(times[i])
        take = conn.execute("SELECT start, end FROM takes WHERE file_id = ? AND start <= ? AND end >= ?",
                            (int(fid), t, t)).fetchone()
        hits.append(Hit(Path(paths[fid]), t, float(scores[i]), tuple(take) if take else None))
    return hits


def fmt_time(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def write_report(query: str, hits: list[Hit], out_html: Path) -> Path:
    thumbs = out_html.parent / "thumbs"
    thumbs.mkdir(parents=True, exist_ok=True)
    rows = []
    for n, h in enumerate(hits, 1):
        thumb = thumbs / f"hit{n}.jpg"
        subprocess.run([_exe("ffmpeg"), "-v", "error", "-y", "-ss", f"{h.time:.3f}", "-i", str(h.path),
                        "-frames:v", "1", "-vf", "scale=360:-2", str(thumb)], check=False)
        take = f"{fmt_time(h.take[0])}–{fmt_time(h.take[1])}" if h.take else "—"
        rows.append(f"<tr><td>{n}</td><td><img src='thumbs/{thumb.name}?v={h.time}'></td>"
                    f"<td><b>{html.escape(h.path.name)}</b><br>момент {fmt_time(h.time)}<br>рабочий участок {take}"
                    f"</td><td>{h.score:.3f}</td></tr>")
    out_html.write_text(
        "<!doctype html><meta charset='utf-8'><title>Поиск</title>"
        "<style>body{font-family:sans-serif;margin:16px}td{padding:6px;vertical-align:top}img{width:360px}</style>"
        f"<h2>{html.escape(query)}</h2><table><tr><th>#</th><th>кадр</th><th>дубль</th><th>сходство</th></tr>"
        + "".join(rows) + "</table>", encoding="utf-8")
    return out_html
