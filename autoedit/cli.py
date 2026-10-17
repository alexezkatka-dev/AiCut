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


def _index_settings(cfg: Config):
    from autoedit.index.indexer import IndexSettings

    return IndexSettings(cfg.models.clip, cfg.models.clip_pretrained, cfg.index.sample_every_sec,
                         cfg.index.sample_width, cfg.index.motion_min, cfg.index.shake)


def _load_embedder(cfg: Config):
    from autoedit.index.embed import Embedder

    typer.echo("Загружаю нейросеть SigLIP (первый раз она скачивается, ~800 МБ)...")
    emb = Embedder(cfg.models.clip, cfg.models.clip_pretrained, cfg.models.clip_device)
    typer.echo(f"Считаю на: {emb.device_name}")
    return emb


@app.command()
def index(folder: Path = typer.Argument(..., help="папка с дублями"),
          project: str = typer.Option(..., help="имя проекта: индекс будет в work/<проект>/media_index.db")) -> None:
    """Проиндексировать дубли: кадры, смысл картинки, резкость, движение, рабочие участки."""
    import time

    from autoedit.index.indexer import index_folder, list_videos

    if not folder.is_dir():
        raise _fail(f"Нет папки с дублями: {folder}")
    if not list_videos(folder):
        raise _fail(f"В папке {folder} нет видео (.mov, .mp4).")
    cfg = load_config()
    t0 = time.monotonic()
    db_path = cfg.work_dir() / project / "media_index.db"
    stats = index_folder(folder, db_path, _index_settings(cfg), lambda: _load_embedder(cfg), typer.echo)
    typer.echo(f"Готово за {time.monotonic() - t0:.1f} с: новых {stats.indexed}, без изменений {stats.skipped}, "
               f"убрано {stats.removed}. Индекс: {db_path}")


@app.command()
def search(query: str = typer.Argument(None, help="что ищем, по-английски; без запроса - спрашивать по очереди"),
           project: str = typer.Option(..., help="имя проекта"),
           top: int = typer.Option(5, help="сколько дублей показать"),
           open_report: bool = typer.Option(True, "--open/--no-open", help="открыть отчёт в браузере")) -> None:
    """Найти дубли по описанию кадра."""
    import webbrowser

    from autoedit.index import db
    from autoedit.search import fmt_time, search as run_search, write_report

    cfg = load_config()
    db_path = cfg.work_dir() / project / "media_index.db"
    if not db_path.is_file():
        raise _fail(f"Нет индекса {db_path}. Сначала запусти индексацию.")
    emb = _load_embedder(cfg)
    conn = db.connect(db_path)
    try:
        while True:
            q = query or input("\nЗапрос по-английски (пустая строка - выход): ").strip()
            if not q:
                break
            hits = run_search(conn, emb.text(q), top)
            for n, h in enumerate(hits, 1):
                typer.echo(f"  {n}. {h.path.name}  момент {fmt_time(h.time)}  сходство {h.score:.3f}")
            report = write_report(q, hits, db_path.parent / "search.html")
            if open_report:
                webbrowser.open(report.resolve().as_uri())
            if query:
                break
    finally:
        conn.close()


if __name__ == "__main__":
    app()
