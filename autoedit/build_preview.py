"""Renders a small preview.mp4 from edit_plan.json with FFmpeg, cut for cut with the CapCut draft.

Every cut lands on frame round(start * fps), so cuts never drift however many clips there are.
Text is drawn with the first font found; without one the preview has no text (a warning is returned).
"""

import re
import shutil
import subprocess
from pathlib import Path

from autoedit.config import Profile
from autoedit.plan import EditPlan, resolve_source

FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]
FONT_COPY = "preview_font.ttf"  # copied next to the output: no path escaping inside the filter


def _exe(name: str) -> str:
    exe = shutil.which(name)
    if exe is None:
        raise FileNotFoundError(f"{name} not found on PATH")
    return exe


def find_font() -> Path | None:
    return next((Path(p) for p in FONT_CANDIDATES if Path(p).is_file()), None)


def preview_size(plan: EditPlan, height: int) -> tuple[int, int]:
    h = height - height % 2
    w = round(h * plan.project.width / plan.project.height / 2) * 2
    return w, h


def has_audio(path: Path) -> bool:
    out = subprocess.run([_exe("ffprobe"), "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout
    return bool(out.strip())


def _filter_script_flag() -> str:
    """FFmpeg 7+ reads an option value from a file with -/opt; older builds use -filter_complex_script."""
    out = subprocess.run([_exe("ffmpeg"), "-hide_banner", "-version"], capture_output=True, text=True).stdout
    m = re.match(r"ffmpeg version n?(\d+)\.", out)
    return "-filter_complex_script" if m and int(m.group(1)) < 7 else "-/filter_complex"


def _atempo(speed: float) -> str:
    # atempo accepts 0.5..2.0 per instance; chain for anything outside.
    parts = []
    while speed > 2.0:
        parts.append("atempo=2.0")
        speed /= 2.0
    while speed < 0.5:
        parts.append("atempo=0.5")
        speed /= 0.5
    parts.append(f"atempo={speed:.6f}")
    return ",".join(parts)


def _black(label: str, w: int, h: int, fps: int, frames: int) -> str:
    return f"color=c=black:s={w}x{h}:r={fps},trim=end_frame={frames},setsar=1,format=yuv420p[{label}]"


def _drawtext(idx: int, style, start: float, end: float, w: int, h: int) -> str:
    size = round(h * style.size / 130)  # rough match to CapCut's font size scale
    border = max(1, round(style.stroke_width / 20 * h / 540))
    y_centre = h / 2 * (1 - style.position_y)
    return (f"drawtext=fontfile={FONT_COPY}:textfile=text_{idx}.txt:expansion=none:fontsize={size}"
            f":fontcolor=0x{style.color.lstrip('#')}:borderw={border}:bordercolor=0x{style.stroke_color.lstrip('#')}"
            f":x=(w-text_w)/2:y={y_centre:.1f}-text_h/2:enable='between(t,{start:.6f},{end:.6f})'")


def build_preview(plan: EditPlan, plan_path: Path, out_path: Path, profile: Profile,
                  height: int = 540) -> list[str]:
    """Writes out_path; returns warnings for the user (empty if none)."""
    warnings: list[str] = []
    fps = plan.project.fps
    w, h = preview_size(plan, height)
    total_frames = round(plan.total_duration * fps)
    out_path = out_path.resolve()  # ffmpeg runs with cwd=out_dir
    out_dir = out_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    inputs: list[str] = []
    graph: list[str] = []
    video_labels: list[str] = []
    audio_labels: list[str] = []
    n_in = 0
    cur = 0  # frames already on the timeline

    for i, v in enumerate(plan.video):
        path = resolve_source(plan_path, v.source).resolve()
        inputs += ["-ss", f"{v.src_in:.6f}", "-t", f"{v.src_duration:.6f}", "-i", str(path)]
        first = max(round(v.start * fps), cur)
        last = max(round(v.end * fps), first + 1)
        if first > cur:
            graph.append(_black(f"gap{i}", w, h, fps, first - cur))
            video_labels.append(f"[gap{i}]")
        zoom = f"({v.zoom_from}+({v.zoom_to - v.zoom_from})*min(t/{v.duration:.6f},1))"
        graph.append(
            f"[{n_in}:v]setpts=(PTS-STARTPTS)/{v.speed},fps={fps},"
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
            f"scale=w='trunc({w}*{zoom}/2)*2':h='trunc({h}*{zoom}/2)*2':eval=frame,crop={w}:{h},"
            f"tpad=stop=-1:stop_mode=clone,trim=end_frame={last - first},setpts=PTS-STARTPTS,"
            f"setsar=1,format=yuv420p[v{i}]")
        video_labels.append(f"[v{i}]")
        if v.volume > 0 and has_audio(path):
            delay = round(first / fps * 1000)
            graph.append(f"[{n_in}:a]asetpts=PTS-STARTPTS,{_atempo(v.speed)},volume={v.volume},"
                         f"adelay=delays={delay}:all=1[va{i}]")
            audio_labels.append(f"[va{i}]")
        n_in += 1
        cur = last

    if total_frames > cur:
        graph.append(_black("tail", w, h, fps, total_frames - cur))
        video_labels.append("[tail]")
    graph.append(f"{''.join(video_labels)}concat=n={len(video_labels)}:v=1:a=0[vcat]")

    texts = []
    if plan.text:
        font = find_font()
        if font is None:
            warnings.append("no font found: preview has no on-screen text")
        else:
            shutil.copyfile(font, out_dir / FONT_COPY)
            for j, t in enumerate(plan.text):
                (out_dir / f"text_{j}.txt").write_text(t.content, encoding="utf-8")
                texts.append(_drawtext(j, profile.text_styles[t.style], t.start, t.end, w, h))
    graph.append(f"[vcat]{','.join(texts) or 'null'}[vout]")

    for k, a in enumerate(plan.audio):
        inputs += ["-ss", f"{a.src_in:.6f}", "-t", f"{a.duration:.6f}", "-i", str(resolve_source(plan_path, a.source).resolve())]
        delay = round(a.start * 1000)
        graph.append(f"[{n_in}:a]asetpts=PTS-STARTPTS,volume={a.volume},adelay=delays={delay}:all=1[a{k}]")
        audio_labels.append(f"[a{k}]")
        n_in += 1

    total = total_frames / fps
    if audio_labels:
        graph.append(f"{''.join(audio_labels)}amix=inputs={len(audio_labels)}:normalize=0:duration=longest,"
                     f"apad,atrim=end={total:.6f}[aout]")
    else:
        graph.append(f"anullsrc=r=48000:cl=stereo,atrim=end={total:.6f}[aout]")

    script = out_dir / "preview_filter.txt"
    script.write_text(";\n".join(graph), encoding="utf-8")
    cmd = [_exe("ffmpeg"), "-v", "error", "-y", *inputs, _filter_script_flag(), script.name,
           "-map", "[vout]", "-map", "[aout]", "-frames:v", str(total_frames),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out_path)]
    # Run inside out_dir so the filter refers to the font and text files by bare name.
    subprocess.run(cmd, cwd=out_dir, check=True)
    return warnings
