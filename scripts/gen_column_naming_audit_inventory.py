# /// script
# requires-python = ">=3.13"
# dependencies = ["pyyaml>=6.0"]
# ///

"""Generate the column naming audit inventory CSV.

Reads every YAML properties file under the kipptaf mart directories
(bridges/dimensions/facts) and emits one CSV row per (model, column) pair
plus pre-populated structural-addition rows for `dim_students` and
`dim_staff`.

Output: docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv

Usage:
    uv run scripts/gen_column_naming_audit_inventory.py

Design reference:
    docs/superpowers/specs/2026-04-15-column-naming-audit.md
"""

from __future__ import annotations

import re

_WS_RE = re.compile(r"\s+")


def _flatten_description(text: str | None) -> str:
    """Collapse whitespace runs to single spaces and strip edges."""
    if not text:
        return ""
    return _WS_RE.sub(" ", text).strip()


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
