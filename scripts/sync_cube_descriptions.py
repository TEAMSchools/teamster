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
from pathlib import Path

import yaml

_COLUMN_RE = re.compile(r"^[a-z_][a-z0-9_]*$")

_DBT_MART_DIRS: tuple[Path, ...] = (
    Path("src/dbt/kipptaf/models/marts/facts/properties"),
    Path("src/dbt/kipptaf/models/marts/dimensions/properties"),
    Path("src/dbt/kipptaf/models/marts/bridges/properties"),
)

_EXPECTED_SCHEMA = "kipptaf_marts"


def _load_dbt_descriptions(
    table: str,
    search_dirs: tuple[Path, ...] | list[Path] = _DBT_MART_DIRS,
) -> dict[str, str] | None:
    """Find ``<table>.yml`` in any of ``search_dirs`` and return
    ``{column_name: description}`` for non-empty descriptions.

    Returns ``None`` if no matching YAML is found.
    """
    for d in search_dirs:
        path = Path(d) / f"{table}.yml"
        if not path.exists():
            continue
        doc = yaml.safe_load(path.read_text()) or {}
        for model in doc.get("models", []) or []:
            if model.get("name") != table:
                continue
            out: dict[str, str] = {}
            for col in model.get("columns", []) or []:
                desc = (col.get("description") or "").strip()
                if desc:
                    out[col["name"]] = desc
            return out
    return None


def _resolve_table_from_sql_table(sql_table: str | None) -> str | None:
    """Extract ``<table>`` from ``kipptaf_marts.<table>``; ``None`` otherwise."""
    if not isinstance(sql_table, str):
        return None
    parts = sql_table.split(".", 1)
    if len(parts) != 2 or parts[0] != _EXPECTED_SCHEMA:
        return None
    return parts[1].strip() or None


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


def _get_ryaml():
    """Lazy-load ruamel.yaml for round-trip YAML editing.

    ruamel.yaml is declared in PEP 723 script dependencies and is available
    when running via ``uv run``. Tests that import this module via importlib
    only call this lazily, so importing the module never imports ruamel.
    """
    # trunk-ignore-begin(pyright/reportMissingImports): PEP 723 dep
    from ruamel.yaml import YAML
    from ruamel.yaml.scalarstring import FoldedScalarString

    # trunk-ignore-end(pyright/reportMissingImports)

    ry = YAML()
    ry.preserve_quotes = True
    ry.width = 80
    ry.indent(mapping=2, sequence=4, offset=2)
    return ry, FoldedScalarString


def _make_description_scalar(text: str, FoldedScalarString):
    """Pick a YAML scalar style for a description string.

    Folded (``>-``) for multi-line or long descriptions to match the style
    already used in Cube and dbt YAMLs; plain string for short single-line.
    """
    if "\n" in text or len(text) > 80:
        return FoldedScalarString(text)
    return text


def _patch_cube_file(
    path: Path,
    *,
    search_dirs: tuple[Path, ...] | list[Path] = _DBT_MART_DIRS,
) -> dict[str, int]:
    """Patch dimensions in a single cube file. Return per-action counts."""
    counts = {
        "updated": 0,
        "skipped_already": 0,
        "skipped_expr": 0,
        "skipped_no_match": 0,
        "skipped_no_table": 0,
    }
    ry, FoldedScalarString = _get_ryaml()
    with path.open() as f:
        doc = ry.load(f)
    cubes = doc.get("cubes") or []
    if not cubes:
        return counts
    cube = cubes[0]
    table = _resolve_table_from_sql_table(cube.get("sql_table"))
    if table is None:
        counts["skipped_no_table"] += 1
        return counts
    descriptions = _load_dbt_descriptions(table, search_dirs=search_dirs)
    if descriptions is None:
        counts["skipped_no_table"] += 1
        return counts
    for dim in cube.get("dimensions") or []:
        if "description" in dim:
            counts["skipped_already"] += 1
            continue
        col = _resolve_dbt_column(dim.get("sql"))
        if col is None:
            counts["skipped_expr"] += 1
            continue
        desc = descriptions.get(col)
        if not desc:
            counts["skipped_no_match"] += 1
            continue
        scalar = _make_description_scalar(desc, FoldedScalarString)
        # Insert ``description:`` immediately after ``name:``.
        keys = list(dim.keys())
        name_idx = keys.index("name") if "name" in keys else 0
        dim.insert(name_idx + 1, "description", scalar)
        counts["updated"] += 1
    if counts["updated"]:
        with path.open("w") as f:
            ry.dump(doc, f)
    return counts
