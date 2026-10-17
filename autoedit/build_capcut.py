"""Builds a new CapCut draft from edit_plan.json with pycapcut 0.0.4 (SPEC §6).

Never modifies existing drafts: every build gets a new AE_<YYYYMMDD-HHMM>_<project> folder.
All media is probed before the draft folder is created, so a failed build leaves nothing behind.
"""

from datetime import datetime
from pathlib import Path

import pycapcut as cc
from pycapcut import KeyframeProperty as KP

from autoedit.config import Profile, TextStyleCfg
from autoedit.plan import EditPlan, resolve_source

AUDIO_TRACKS = {"voiceover": "audio_vo", "music": "audio_music", "sfx": "audio_sfx"}
US = 1_000_000


def unique_draft_name(drafts_dir: Path, project: str, now: datetime, prefix: str = "AE_") -> str:
    """<prefix><YYYYMMDD-HHMM>_<project>, with a numeric suffix if taken. Never reuses a name."""
    base = f"{prefix}{now:%Y%m%d-%H%M}_{project}"
    name, n = base, 2
    while (drafts_dir / name).exists():
        name, n = f"{base}_{n}", n + 1
    return name


def _us(seconds: float) -> int:
    return round(seconds * US)


def _rgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"colour must look like #RRGGBB, got {hex_color!r}")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _text_segment(content: str, timerange: cc.Timerange, s: TextStyleCfg) -> cc.TextSegment:
    return cc.TextSegment(
        content, timerange,
        style=cc.TextStyle(size=s.size, bold=s.bold, color=_rgb(s.color), align=1, auto_wrapping=True),
        border=cc.TextBorder(color=_rgb(s.stroke_color), width=s.stroke_width),
        clip_settings=cc.ClipSettings(transform_y=s.position_y),
    )


def _video_segments(plan: EditPlan, plan_path: Path) -> tuple[list[cc.VideoSegment], bool]:
    """Returns segments and whether the main track is gapless from 0 (CapCut's magnet would close gaps)."""
    segments, prev_end, gapless = [], 0, True
    for v in plan.video:
        # Clamp to the previous end so rounding never makes neighbours overlap by a microsecond.
        start = max(_us(v.start), prev_end)
        gapless = gapless and start - prev_end <= _us(0.5 / plan.project.fps)
        src = cc.Timerange(_us(v.src_in), _us(v.src_duration))
        path = resolve_source(plan_path, v.source)
        try:
            # With both source range and speed set, pycapcut derives the timeline length itself.
            seg = cc.VideoSegment(path.as_posix(), cc.Timerange(start, 1), source_timerange=src,
                                  speed=v.speed, volume=v.volume)
        except ValueError as e:
            raise ValueError(f"video {v.slot_id}: {path.name} is shorter than src_out = {v.src_out}s") from e
        if v.zoom_from != v.zoom_to:
            seg.add_keyframe(KP.uniform_scale, 0, v.zoom_from)
            seg.add_keyframe(KP.uniform_scale, seg.target_timerange.duration - 1, v.zoom_to)
        elif v.zoom_from != 1.0:
            seg.clip_settings.scale_x = seg.clip_settings.scale_y = v.zoom_from
        segments.append(seg)
        prev_end = seg.target_timerange.end
    return segments, gapless


def build_draft(plan: EditPlan, plan_path: Path, drafts_dir: Path, profile: Profile,
                now: datetime | None = None, prefix: str = "AE_") -> Path:
    unknown = sorted({t.style for t in plan.text} - set(profile.text_styles))
    if unknown:
        raise ValueError(f"text style(s) {unknown} not in profile '{plan.project.profile}' "
                         f"(has {sorted(profile.text_styles)})")

    video, gapless = _video_segments(plan, plan_path)
    audio = [(AUDIO_TRACKS[a.kind],
              cc.AudioSegment(resolve_source(plan_path, a.source).as_posix(),
                              cc.Timerange(_us(a.start), _us(a.duration)),
                              source_timerange=cc.Timerange(_us(a.src_in), _us(a.duration)),
                              volume=a.volume))
             for a in plan.audio]
    texts = [_text_segment(t.content, cc.Timerange(_us(t.start), _us(t.duration)), profile.text_styles[t.style])
             for t in plan.text]

    p = plan.project
    name = unique_draft_name(drafts_dir, p.name, now or datetime.now(), prefix)
    script = cc.DraftFolder(str(drafts_dir)).create_draft(name, p.width, p.height, p.fps, maintrack_adsorb=gapless)

    script.add_track(cc.TrackType.video, "video_main")
    for seg in video:
        script.add_segment(seg, "video_main")
    for kind, track in AUDIO_TRACKS.items():
        if any(a.kind == kind for a in plan.audio):
            script.add_track(cc.TrackType.audio, track)
    for track, seg in audio:
        script.add_segment(seg, track)
    if texts:
        script.add_track(cc.TrackType.text, "text_overlay")
        for seg in texts:
            script.add_segment(seg, "text_overlay")

    script.save()
    return drafts_dir / name
