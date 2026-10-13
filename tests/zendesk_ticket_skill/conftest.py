"""Put the skill's scripts folder and the article skill's fakes on sys.path.

Scoped to this directory, following tests/zendesk_help_articles/conftest.py.
"""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_root / ".claude" / "skills" / "zendesk-tickets" / "scripts"))
sys.path.insert(0, str(_root / "tests" / "zendesk_help_articles"))
