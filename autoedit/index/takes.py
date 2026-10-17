"""Active parts of a clip: something moves, but the camera is not shaking (hand reaching for the phone)."""

import numpy as np


def find_takes(motion: list[float], every: float, duration: float, motion_min: float, shake: float,
               min_len: float = 1.0, merge_gap: float = 1.0) -> list[tuple[float, float]]:
    m = np.asarray(motion, np.float32)
    if len(m) >= 3:
        # Median of 3: drops one-sample blips without widening the edges of real action.
        padded = np.pad(m, 1, mode="edge")
        m = np.median(np.stack([padded[:-2], padded[1:-1], padded[2:]]), axis=0)
    active = (m >= motion_min) & (m <= shake)

    runs: list[list[float]] = []
    for i, on in enumerate(active):
        if not on:
            continue
        start, end = i * every, min((i + 1) * every, duration)
        if runs and start - runs[-1][1] <= merge_gap:
            runs[-1][1] = end
        else:
            runs.append([start, end])
    takes = [(round(s, 3), round(e, 3)) for s, e in runs if e - s >= min_len]
    if takes:
        return takes
    # Nothing clearly active (e.g. a still overhead shot): keep the clip minus its very edges.
    edge = min(0.5, duration / 4)
    return [(round(edge, 3), round(duration - edge, 3))]
