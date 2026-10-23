"""Loads scripts/cube_validate as the package `cube_validate` for these tests.

scripts/ has no __init__.py by design, and tests/scripts/ is itself a package
named `scripts`, so the tool is registered under its own name instead.
"""

import importlib.util
import sys
from pathlib import Path

PKG = Path(__file__).parents[3] / "scripts" / "cube_validate"


def _load() -> None:
    if "cube_validate" in sys.modules:
        return
    spec = importlib.util.spec_from_file_location(
        "cube_validate", PKG / "__init__.py", submodule_search_locations=[str(PKG)]
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Registered before exec_module so dataclasses and relative imports resolve.
    sys.modules["cube_validate"] = mod
    spec.loader.exec_module(mod)


_load()
