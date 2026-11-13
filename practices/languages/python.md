# Python

- Python 3.12+ with `uv` (`uv sync`, `uv run`, `uv add`), never ad-hoc `pip` or `venv`; commit `uv.lock`, and CI runs `uv sync --locked`. {core; initial}
- Never use `yaml.load` (use `safe_load`), `pickle` on untrusted data, `subprocess` with `shell=True`, or untrusted XML without `defusedxml`. {gate: ruff S; initial}
- Ruff for lint and format (line length 100, rules `E, F, I, UP, B, SIM` as a baseline) and pytest for tests. Type hints on every public function; a project may require `mypy --strict`. {topic; initial}
- Use `src/` layout. Enforce package import rules with a test that parses imports with `ast` (see `templates/python/test_layout.py`), not by convention alone. {topic; initial}
- Prefer `pytest.mark.parametrize` for table-style cases. Fake HTTP with `respx` (httpx) or a fake adapter object. {topic; initial}
- Validate data at the boundary with Pydantic v2 models (or attrs for internal values); load settings with `pydantic-settings` from the environment. {topic; initial}
- Use the standard `logging` module, never `print`, in library code. Log ids and counts, not payloads. {topic; initial}
- A framework-specific virtualenv (for example Airflow in a dev container) can be wiped by `uv sync`/`uv run`; such projects document `--inexact` or `--no-sync` in their CLAUDE.md. {topic; initial}
