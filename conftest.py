from __future__ import annotations

import sys
from pathlib import Path

# Add the project root to sys.path so that `scripts.*` modules are importable.
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
