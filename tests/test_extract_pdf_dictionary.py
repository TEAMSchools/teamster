"""Unit tests for scripts/extract_pdf_dictionary.py.

The script filename uses underscores specifically so we can import it.
We use importlib.util rather than changing project-wide pytest config,
keeping the import pattern local to this test file.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "extract_pdf_dictionary.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("extract_pdf_dictionary", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_module_loads() -> None:
    module = _load_script()
    assert callable(module.main)
