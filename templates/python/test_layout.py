"""Import rules between the project's packages, enforced by parsing imports.

Copy into tests/ and edit RULES: each package maps to the first-party packages it must not import.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
FIRST_PARTY = "myproject"  # the top-level package under src/

# package (dotted, relative to FIRST_PARTY) -> packages it must not import
RULES: dict[str, set[str]] = {
    "schemas": {"api", "extractor"},
    "extractor": {"api"},
}


def imported_modules(package: str) -> set[str]:
    """First-party subpackages imported anywhere under src/FIRST_PARTY/<package>."""
    found: set[str] = set()
    for path in (SRC / FIRST_PARTY / package.replace(".", "/")).rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            for name in names:
                parts = name.split(".")
                if parts[0] == FIRST_PARTY and len(parts) > 1:
                    found.add(parts[1])
    return found


@pytest.mark.parametrize(("package", "forbidden"), sorted(RULES.items()))
def test_import_rules(package: str, forbidden: set[str]) -> None:
    if not (SRC / FIRST_PARTY / package).exists():
        pytest.skip(f"{package} does not exist yet")
    assert imported_modules(package).isdisjoint(forbidden)
