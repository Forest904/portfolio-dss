import ast
from pathlib import Path

DOMAIN_ROOT = Path(__file__).parents[1] / "app" / "domain"
APPLICATION_ROOT = Path(__file__).parents[1] / "app" / "application"
FORBIDDEN_IMPORT_PREFIXES = (
    "fastapi",
    "pydantic",
    "pandas",
    "yfinance",
    "app.api",
    "app.application",
    "app.core",
    "app.infrastructure",
)


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_domain_has_no_outward_or_framework_dependencies() -> None:
    violations: list[str] = []
    for path in DOMAIN_ROOT.rglob("*.py"):
        for module in imported_modules(path):
            if module.startswith(FORBIDDEN_IMPORT_PREFIXES):
                violations.append(f"{path.relative_to(DOMAIN_ROOT)} imports {module}")

    assert violations == []


def test_application_does_not_depend_on_api_core_or_infrastructure() -> None:
    forbidden = ("fastapi", "app.api", "app.core", "app.infrastructure")
    violations: list[str] = []
    for path in APPLICATION_ROOT.rglob("*.py"):
        for module in imported_modules(path):
            if module.startswith(forbidden):
                violations.append(f"{path.relative_to(APPLICATION_ROOT)} imports {module}")

    assert violations == []
