# /// script
# requires-python = ">=3.13"
# dependencies = ["pyyaml>=6.0", "ruamel.yaml>=0.18"]
# ///

"""Sync dbt mart YAML descriptions into Cube cube YAML files.

Reads each cube file under ``src/cube/model/cubes/``, locates the matching
dbt mart YAML via ``sql_table:``, and inserts dbt column descriptions onto
cube dimensions that lack them. Patches dimensions only — measures are
calculations and require hand-authored descriptions. Existing Cube
descriptions are preserved.

Usage:
    uv run scripts/sync_cube_descriptions.py [--check]
"""

from __future__ import annotations

import re

_COLUMN_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def _resolve_dbt_column(sql: str | None) -> str | None:
    """Return the dbt column name from a Cube dimension's ``sql:`` value.

    Handles bare column (``col``), ``{CUBE}``-qualified
    (``{CUBE}.col``), and backticked (`col`, ``{CUBE}.`col``).
    Returns ``None`` for SQL expressions or non-string input.
    """
    if not isinstance(sql, str):
        return None
    s = sql.strip()
    if s.startswith("{CUBE}."):
        s = s[len("{CUBE}.") :]
    s = s.strip("`").strip()
    return s if _COLUMN_RE.match(s) else None
