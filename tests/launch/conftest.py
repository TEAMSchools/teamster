"""Put `docs/` on sys.path so tests can `import launch.build`.

docs/launch has no __init__.py and does not need one — it resolves as a
PEP 420 namespace package. Scoped to this directory so the other 749
collected tests are unaffected.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "docs"))
