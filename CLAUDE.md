# Auto Editor

Local Windows tool that turns raw phone footage + a voiceover script (mode A) or a reference video (mode B) into a CapCut draft and a preview MP4. Full spec: `docs/SPEC.md` — read it before any work. Stage log: `docs/PROGRESS.md`.

## Who you are working with
- The user (Sasha) is a YouTube creator, not a programmer. Talk to him in **Russian**, plainly. Code, identifiers and comments in English.
- When he must do something, give exact steps: what to click, what to paste into PowerShell, what he should see. One step at a time.
- He judges the result by opening the draft in CapCut. Ask him for that check at the end of each stage, and ask how much manual fixing was left.

## Environment
- Windows 10/11, PowerShell, Python 3.11 in `.venv`, FFmpeg on PATH.
- CapCut **International** desktop. Drafts folder from `config.yaml` (`capcut.drafts_dir`).
- Paths can contain spaces and Cyrillic: always pass subprocess args as a list, use `pathlib`, UTF-8 everywhere.

## Hard rules
1. Work stage by stage per `docs/SPEC.md` §9. Do not start the next stage until the current acceptance criterion is met and recorded in `docs/PROGRESS.md`. No features beyond the current stage.
2. `pycapcut==0.0.4` is pinned. Do not upgrade (0.1.0 removes `add_track`). Base CapCut code on the verified snippet in SPEC §6.
3. Never modify or overwrite existing CapCut drafts. Only create new ones named `AE_<YYYYMMDD-HHMM>_<project>`.
4. Never modify, move or re-encode the user's source footage. Read only.
5. `edit_plan.json` is the single contract between planning and building. Builders read only the plan; planners never touch CapCut.
6. Every pipeline step writes its output to `work/<project>/` and is cacheable and re-runnable on its own.
7. All AI runs locally (faster-whisper, open_clip SigLIP). No paid APIs unless the user explicitly turns them on (stage 6).
8. Large media never goes into git. `work/`, `.venv/`, `*.mp4`, `*.mov`, `*.mp3` are in `.gitignore`.

## Workflow per stage
1. Re-read the stage row in SPEC §9 and restate the acceptance criterion to the user in one sentence.
2. Implement with tests. Synthetic clips for tests come from `tests/make_samples.py` (FFmpeg `testsrc` / `sine`).
3. Run `pytest` and a real run on the user's sample folder if he provided one.
4. Tell the user exactly how to check the result in CapCut.
5. Append to `docs/PROGRESS.md`: date, stage, what was built, the measured result, known issues.
6. Commit to git with a clear message.

## Commands
- Install: `install.bat` (creates `.venv`, installs `requirements.txt`, checks `ffmpeg -version`).
- Run UI: `run.bat` → Gradio on http://127.0.0.1:7860.
- CLI: `python -m autoedit.cli <command>` (`index`, `plan-vo`, `plan-ref`, `match`, `build`, `preview`, `all`).
- Tests: `.venv\Scripts\python -m pytest -q`.
