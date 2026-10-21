# Python practices (cc-practices plugin)

- Python 3.12+, `uv` for environments and dependencies (`uv sync`, `uv run ...`, `uv add`), never ad-hoc `pip` or `venv`. Commit `uv.lock`; CI runs `uv sync --locked`.
- Ruff for lint and format (line length 100, rules `E, F, I, UP, B, SIM` as a baseline) and pytest for tests. Type hints on every public function; a project may require `mypy --strict`.
- Use `src/` layout. Enforce package import rules with a test that parses imports with `ast` (see `templates/python/test_layout.py`), not by convention alone.
- Prefer `pytest.mark.parametrize` for table-style cases. Fake HTTP with `respx` (httpx) or a fake adapter object; tests must pass offline.
- Validate data at the boundary with Pydantic v2 models (or attrs for internal values); load settings with `pydantic-settings` from the environment.
- Use the standard `logging` module, never `print`, in library code. Log ids and counts, not payloads.
- Avoid `yaml.load` (use `safe_load`), `pickle` on untrusted data, `subprocess` with `shell=True`, and parsing untrusted XML without `defusedxml`.
- A framework-specific virtualenv (for example Airflow in a dev container) can be wiped by `uv sync`/`uv run`; such projects document `--inexact` or `--no-sync` in their CLAUDE.md.
