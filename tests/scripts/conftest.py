from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is on sys.path so `scripts.*` is importable.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
