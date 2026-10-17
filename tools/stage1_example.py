"""Stage 1 check: examples/edit_plan.example.json with stand-in clips -> CapCut draft + preview.mp4.

Run: .venv\\Scripts\\python -m tools.stage1_example
Messages are in Russian: the user reads them.
"""

import shutil
import sys

import typer

from autoedit.build_capcut import build_draft
from autoedit.build_preview import build_preview
from autoedit.cli import drafts_dir_or_exit, load_checked
from autoedit.config import ROOT, load_config
from tests.make_samples import make_example_media

EXAMPLE_PLAN = ROOT / "examples" / "edit_plan.example.json"


def main() -> int:
    cfg = load_config()
    project_dir = cfg.work_dir() / "example"
    plan_path = project_dir / "edit_plan.json"
    print("Делаю тестовые клипы вместо исходников из примера...")
    try:
        make_example_media(project_dir)
    except FileNotFoundError:
        print("FFmpeg не найден. Запусти install.bat ещё раз.")
        return 1
    shutil.copyfile(EXAMPLE_PLAN, plan_path)

    try:
        plan, profile, cfg = load_checked(plan_path)
        drafts = drafts_dir_or_exit(cfg)
    except typer.Exit as e:
        return e.exit_code
    print("Собираю черновик CapCut...")
    draft = build_draft(plan, plan_path, drafts, profile, prefix=cfg.capcut.draft_prefix)
    print("Собираю превью...")
    preview = project_dir / "preview.mp4"
    for w in build_preview(plan, plan_path, preview, profile, cfg.preview.height):
        print(f"Внимание: {w}")

    print()
    print(f"ГОТОВО. Черновик: {draft.name}")
    print(f"Превью: {preview}")
    print()
    print("Склейки по плану (секунды):")
    for v in plan.video:
        print(f"  {v.slot_id}: {v.start:.2f} - {v.end:.2f}  {v.source}, с {v.src_in:.2f} с, наезд {v.zoom_from} -> {v.zoom_to}")
    for t in plan.text:
        print(f"  надпись \"{t.content}\": {t.start:.2f} - {t.end:.2f}")
    print()
    print("Что проверить:")
    print("1. Если CapCut открыт - выйди на главный экран. Есть в списке новый черновик? Если нет - перезапусти CapCut.")
    print("2. В черновике: K01 начинается со счётчика 124 (12,4 с исходника), K02 - с 40, склейка на 2,84 с.")
    print("3. Открой превью: склейка там же, на 2,84 с, счётчики те же, надпись в начале.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
