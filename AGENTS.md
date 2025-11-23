# Repository Guidelines

## Project Structure & Module Organization
- Source code: `src/alist_mikananirss/`
  - `core/` (RSS monitor, renamer, remapper, download manager)
  - `alist/` (Alist API + tasks), `websites/`, `extractor/`, `utils/`, `common/`, `bot/`
  - Web UI: `webui/` (FastAPI server, templates, static)
- Entrypoints: `src/alist_mikananirss/main.py`, `src/alist_mikananirss/__main__.py`
- Tests: `tests/` (mirrors module layout)
- Config examples: `config.yaml.example`, `full_config.yaml.example`
- Packaging/CI: `pyproject.toml`, `.github/workflows/`

## Build, Test, and Development Commands
- Create env and install: `uv sync --dev`
- Run WebUI: `uv run alist-mikananirss-webui --host 0.0.0.0 --port 8080`
- Run CLI: `uv run alist-mikananirss --config config.yaml`
- Tests (all): `uv run -m pytest -q`
- Tests (WebUI quick): `uv run -m pytest test_webui.py -q`
- Lint: `uv run ruff check .`
- Format: `uv run black .` (check only: `--check`)

## Coding Style & Naming Conventions
- Python ≥ 3.11, 4-space indentation, UTF-8.
- Format with Black (default line length 88). Lint with Ruff.
- Naming: modules/files `snake_case`, classes `CamelCase`, functions/vars `snake_case`.
- Keep functions small and async-friendly; prefer explicit types where helpful.

## Testing Guidelines
- Frameworks: `pytest`, `pytest-asyncio`.
- Place tests under `tests/<module>/test_*.py`; name async tests with `@pytest.mark.asyncio`.
- Provide unit tests for new features/bug fixes; keep tests deterministic and fast.

## Commit & Pull Request Guidelines
- Conventional Commits style is used in history, e.g. `feat(webui): ...`, `fix(core): ...`, `docs(...): ...`, `ci: ...`, `refactor(...): ...`.
- PRs should: include clear description, link related issues, update tests/docs, attach screenshots for WebUI changes, and pass CI (lint + tests).
- Keep PRs focused and small; avoid unrelated refactors.

## Security & Configuration Tips
- Do not commit secrets; `*.yaml` is git-ignored. Copy from `config.yaml.example` for local runs.
- Protect admin routes when exposing WebUI; prefer reverse-proxy auth/whitelists.
- Use `uv` instead of `pip` for reproducible envs.

## GitHub Workflow
- Prefer GitHub CLI for reviews: `gh pr create --fill`, `gh pr status`, `gh pr view -w`.
