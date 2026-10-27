import importlib.util
import sys
from pathlib import Path

# `tests/scripts/__init__.py` makes `scripts` resolve to the test package, so
# load the package under its own top-level name instead.
_pkg_dir = Path(__file__).resolve().parents[3] / "scripts" / "cube_validation"

if "cube_validation" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "cube_validation",
        _pkg_dir / "__init__.py",
        submodule_search_locations=[str(_pkg_dir)],
    )
    assert _spec is not None and _spec.loader is not None
    _module = importlib.util.module_from_spec(_spec)
    sys.modules["cube_validation"] = _module
    _spec.loader.exec_module(_module)
