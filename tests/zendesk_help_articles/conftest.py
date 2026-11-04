"""Put the skill's scripts folder on sys.path so tests can `import publish_article`.

Scoped to this directory, following tests/launch/conftest.py.
"""

import sys
from pathlib import Path

sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parents[2]
        / ".claude"
        / "skills"
        / "zendesk-help-articles"
        / "scripts"
    ),
)
