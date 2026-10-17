"""Command line: python -m autoedit.cli <command>. Messages are in Russian: the user reads them."""

from pathlib import Path

import typer
from pydantic import ValidationError

from autoedit.build_capcut import build_draft
from autoedit.build_preview import build_preview
from autoedit.config import Config, Profile, load_config, load_profile
from autoedit.plan import EditPlan, load_plan, missing_sources

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Auto Editor")


def _fail(msg: str) -> typer.Exit:
    typer.echo(msg, err=True)
    return typer.Exit(1)


def load_checked(plan_path: Path) -> tuple[EditPlan, Profile, Config]:
    """Plan, its profile and the config, or a clear message and exit code 1."""
    try:
        plan = load_plan(plan_path)
    except FileNotFoundError:
        raise _fail(f"Не нашёл монтажный план: {plan_path}")
    except ValidationError as e:
        raise _fail(f"Ошибка в монтажном плане {plan_path}:\n{e}")
    missing = missing_sources(plan, plan_path)
    if missing:
        raise _fail("Нет файлов, на которые ссылается план:\n" + "\n".join(f"  {p}" for p in missing))
    try:
        profile = load_profile(plan.project.profile)
    except FileNotFoundError:
        raise _fail(f"Нет профиля profiles/{plan.project.profile}.yaml")
    if plan.subtitles:
        typer.echo("Внимание: субтитры появятся на этапе 6, сейчас поле subtitles пропускается.")
    return plan, profile, load_config()


def drafts_dir_or_exit(cfg: Config) -> Path:
    drafts = cfg.drafts_dir()
    if drafts is None or not drafts.is_dir():
        raise _fail(f"Не нашёл папку черновиков CapCut: {drafts}\n"
                    "Впиши правильный путь в config.yaml (capcut: drafts_dir:) и запусти снова.")
    return drafts


@app.command()
def build(plan_path: Path = typer.Argument(..., help="edit_plan.json")) -> None:
    """Собрать новый черновик CapCut по монтажному плану."""
    plan, profile, cfg = load_checked(plan_path)
    try:
        draft = build_draft(plan, plan_path, drafts_dir_or_exit(cfg), profile, prefix=cfg.capcut.draft_prefix)
    except ValueError as e:
        raise _fail(f"Черновик не собран: {e}")
    typer.echo(f"Черновик: {draft.name}")


@app.command()
def preview(plan_path: Path = typer.Argument(..., help="edit_plan.json"),
            out: Path = typer.Option(None, help="куда сохранить (по умолчанию preview.mp4 рядом с планом)")) -> None:
    """Собрать preview.mp4 по монтажному плану."""
    plan, profile, cfg = load_checked(plan_path)
    out = out or plan_path.parent / "preview.mp4"
    for w in build_preview(plan, plan_path, out, profile, cfg.preview.height):
        typer.echo(f"Внимание: {w}")
    typer.echo(f"Превью: {out}")


if __name__ == "__main__":
    app()
