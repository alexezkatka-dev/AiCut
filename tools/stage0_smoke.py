"""Stage 0: build a test CapCut draft (2 trimmed clips, zoom, voiceover, text) per SPEC §6.

Run: .venv\\Scripts\\python -m tools.stage0_smoke [DRAFTS_DIR]
Messages are in Russian: the user reads them.
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import pycapcut as cc
from pycapcut import KeyframeProperty as KP
from pycapcut import trange_seconds as ts

from tests.make_samples import make_samples

ROOT = Path(__file__).resolve().parent.parent
MEDIA_DIR = ROOT / "work" / "stage0" / "media"

# (media key, src_in, duration, zoom_to); zoom always starts at 1.00.
CLIPS = [("clip1", 1.0, 3.0, 1.12), ("clip2", 2.5, 3.0, 1.06)]
TITLE = ("DRY AGAIN?", 0.0, 2.0)  # text, start, duration


def default_drafts_dir() -> Path | None:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    return Path(local) / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"


def unique_draft_name(drafts_dir: Path, project: str, now: datetime) -> str:
    """AE_<YYYYMMDD-HHMM>_<project>, with a numeric suffix if taken. Never reuses a name."""
    base = f"AE_{now:%Y%m%d-%H%M}_{project}"
    name, n = base, 2
    while (drafts_dir / name).exists():
        name, n = f"{base}_{n}", n + 1
    return name


def build_smoke_draft(drafts_dir: Path, media: dict[str, Path], now: datetime | None = None) -> Path:
    name = unique_draft_name(drafts_dir, "smoke", now or datetime.now())
    script = cc.DraftFolder(str(drafts_dir)).create_draft(name, 1920, 1080, 30)
    script.add_track(cc.TrackType.video, "video_main")
    script.add_track(cc.TrackType.audio, "audio_vo")
    script.add_track(cc.TrackType.text, "text_overlay")

    start = 0.0
    for key, src_in, dur, zoom_to in CLIPS:
        # CapCut stores media paths with forward slashes.
        seg = cc.VideoSegment(media[key].as_posix(), ts(start, duration=dur),
                              source_timerange=ts(src_in, duration=dur))
        seg.add_keyframe(KP.uniform_scale, 0, 1.00)
        seg.add_keyframe(KP.uniform_scale, cc.tim(f"{dur}s") - 1, zoom_to)
        script.add_segment(seg, "video_main")
        start += dur

    script.add_segment(cc.AudioSegment(media["vo"].as_posix(), ts(0, duration=start)), "audio_vo")
    text, t_start, t_dur = TITLE
    script.add_segment(cc.TextSegment(text, ts(t_start, duration=t_dur)), "text_overlay")
    script.save()
    return drafts_dir / name


def inspect_user_drafts(drafts_dir: Path) -> tuple[int, int]:
    """Read-only: count the user's drafts whose content file is plain JSON vs. not (encrypted)."""
    plain = other = 0
    for draft in drafts_dir.iterdir():
        if not draft.is_dir() or draft.name.startswith("AE_"):
            continue
        for fname in ("draft_content.json", "draft_info.json"):
            path = draft / fname
            if not path.is_file():
                continue
            try:
                json.loads(path.read_text(encoding="utf-8"))
                plain += 1
            except (UnicodeDecodeError, json.JSONDecodeError):
                other += 1
            except OSError:
                pass  # locked or unreadable: says nothing about encryption
            break
    return plain, other


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 0: test CapCut draft")
    parser.add_argument("drafts_dir", nargs="?", help="CapCut drafts folder (default: standard location)")
    args = parser.parse_args(argv)

    drafts_dir = Path(args.drafts_dir) if args.drafts_dir else default_drafts_dir()
    if drafts_dir is None or not drafts_dir.is_dir():
        print(f"Не нашёл папку черновиков CapCut: {drafts_dir}")
        print("В настройках CapCut найди, где хранятся черновики (Draft location), скопируй путь")
        print('и запусти в PowerShell из папки проекта:  .\\stage0.bat "ПУТЬ_К_ПАПКЕ"')
        return 1

    print("Делаю тестовые клипы через FFmpeg...")
    try:
        media = make_samples(MEDIA_DIR)
    except FileNotFoundError:
        print("FFmpeg не найден. Выполни в PowerShell:  winget install Gyan.FFmpeg  и открой окно заново.")
        return 1

    print("Собираю черновик...")
    draft = build_smoke_draft(drafts_dir, media)
    plain, other = inspect_user_drafts(drafts_dir)

    print()
    print(f"ГОТОВО. Создан черновик: {draft.name}")
    print(f"Папка черновиков: {drafts_dir}")
    print(f"Тестовые клипы: {MEDIA_DIR} (не удаляй, черновик ссылается на них)")
    print(f"Твои проекты CapCut: {plain} читаются как обычный текст, {other} - нет (похоже, зашифрованы).")
    print()
    print("Что проверить в CapCut:")
    print("1. Если CapCut открыт - выйди на главный экран. Есть в списке AE_..._smoke? Запомни ответ.")
    print("2. Если нет - закрой CapCut полностью и открой снова.")
    print("3. Открой черновик и проиграй: 6 секунд, два клипа по 3 с, у второго другие цвета.")
    print("   Счётчик в кадре: первый клип начинается с 10, второй с 25 (это 1,0 с и 2,5 с).")
    print("   Плавный наезд на обоих клипах, тон на отдельной звуковой дорожке, надпись DRY AGAIN? первые 2 с.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
