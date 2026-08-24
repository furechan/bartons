"""Read the public surfaces declared by indicator implementation modules."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "python" / "bartons" / "indicators"
INIT = PACKAGE / "__init__.py"


def implementation_modules() -> list[str]:
    """Return star-imported implementation modules in package order."""
    tree = ast.parse(INIT.read_text())
    return [
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.level == 1
        and node.module is not None
        and any(alias.name == "*" for alias in node.names)
    ]


def module_exports(module: str) -> tuple[str, ...]:
    """Read one implementation module's literal ``__all__`` declaration."""
    path = PACKAGE / f"{module.replace('.', '/')}.py"
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if isinstance(value, (list, tuple)) and all(
                isinstance(name, str) for name in value
            ):
                return tuple(value)
            break
    raise RuntimeError(f"{path} must declare a literal __all__ of strings")


def indicator_exports() -> list[tuple[str, tuple[str, ...]]]:
    """Return ``(module, exported names)`` pairs in package order."""
    return [(module, module_exports(module)) for module in implementation_modules()]
