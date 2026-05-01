# /// script
# requires-python = ">=3.13"
# dependencies = ["pyyaml>=6.0"]
# ///

"""Sync dbt column descriptions and PII flags into Cube dimension YAML files.

Reads a dbt manifest.json and patches `description:` and `meta: {pii: true}`
into Cube dimension YAML files for dimensions that are direct column references
(i.e. `name == sql`). Computed dimensions, joins, and measures are never
touched.

The patch is text-level: only the target lines are inserted or replaced;
every other byte in the file is written back unchanged.

Prerequisites:
    uv run scripts/dbt-manifest.py  # ensure manifest exists at target path

Usage:
    uv run scripts/sync-cube-descriptions.py --manifest <path-to-manifest.json>
    uv run scripts/sync-cube-descriptions.py  # uses DBT_MANIFEST_PATH env var
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

CUBE_DIR = Path(__file__).parent.parent / "src" / "cube" / "model" / "cubes"
DIM_ITEM_INDENT = 6  # "      - name: ..."
DIM_FIELD_INDENT = 8  # "        sql: ..."


def load_manifest(path: Path) -> dict[str, dict[str, dict]]:
    """Return {model_name: {col_name: {description, pii}}} from manifest."""
    manifest = json.loads(path.read_text())
    result: dict[str, dict[str, dict]] = {}
    for node in manifest.get("nodes", {}).values():
        if node.get("resource_type") != "model":
            continue
        cols: dict[str, dict] = {}
        for col_name, col in node.get("columns", {}).items():
            cols[col_name] = {
                "description": (col.get("description") or "").strip(),
                "pii": bool((col.get("meta") or {}).get("contains_pii")),
            }
        result[node["name"]] = cols
    return result


def direct_dims(cube_data: dict, manifest_cols: dict[str, dict]) -> dict[str, dict]:
    """Return {dim_name: {description, pii}} for dims where name == sql."""
    updates: dict[str, dict] = {}
    for dim in cube_data.get("dimensions", []):
        name = dim["name"]
        sql = str(dim.get("sql", "")).strip()
        if name == sql and name in manifest_cols:
            updates[name] = manifest_cols[name]
    return updates


def patch_file(path: Path, updates: dict[str, dict]) -> bool:
    """
    Rewrite path inserting/replacing description and meta lines for each dim
    in updates. Returns True if the file was modified.

    Algorithm: line-by-line state machine. Tracks which dimension block the
    cursor is in. When it sees `type:` for an updatable dimension, it emits
    the type line, skips any existing description/meta lines, then injects
    the new values. Everything else is emitted byte-for-byte unchanged.
    """
    text = path.read_text()
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    current_dim: str | None = None
    i = 0

    while i < len(lines):
        line = lines[i]
        raw = line.rstrip("\n").rstrip("\r")
        stripped = raw.lstrip()
        indent = len(raw) - len(stripped)

        # ── dimension list item: "      - name: <dim>" ────────────────────
        if indent == DIM_ITEM_INDENT and stripped.startswith("- name: "):
            dim_name = stripped[len("- name: ") :].strip()
            current_dim = dim_name if dim_name in updates else None
            result.append(line)
            i += 1
            continue

        # ── leaving an updatable block (non-comment, non-blank, indent ≤ 6) ─
        if (
            current_dim is not None
            and indent <= DIM_ITEM_INDENT
            and stripped
            and not stripped.startswith("#")
        ):
            current_dim = None

        # ── pass through everything outside an updatable dimension ──────────
        if current_dim is None:
            result.append(line)
            i += 1
            continue

        # ── inside an updatable dimension block ─────────────────────────────

        # Skip existing description: (single-line or block scalar)
        if indent == DIM_FIELD_INDENT and stripped.startswith("description:"):
            i += 1
            while i < len(lines):
                cont = lines[i].rstrip("\n").rstrip("\r")
                cont_stripped = cont.lstrip()
                cont_indent = len(cont) - len(cont_stripped)
                if cont_stripped and cont_indent > DIM_FIELD_INDENT:
                    i += 1  # continuation line of block scalar
                else:
                    break
            continue

        # Skip existing meta: block
        if indent == DIM_FIELD_INDENT and stripped.startswith("meta:"):
            i += 1
            while i < len(lines):
                cont = lines[i].rstrip("\n").rstrip("\r")
                cont_stripped = cont.lstrip()
                cont_indent = len(cont) - len(cont_stripped)
                if cont_stripped and cont_indent > DIM_FIELD_INDENT:
                    i += 1
                else:
                    break
            continue

        # Emit the line; if it's the `type:` line, inject metadata after it
        result.append(line)
        i += 1

        if indent == DIM_FIELD_INDENT and stripped.startswith("type:"):
            update = updates[current_dim]
            field_pad = " " * DIM_FIELD_INDENT
            if update["description"]:
                desc = update["description"].replace('"', '\\"')
                result.append(f'{field_pad}description: "{desc}"\n')
            if update["pii"]:
                result.append(f"{field_pad}meta:\n")
                result.append(f"{field_pad}  pii: true\n")

    new_text = "".join(result)
    if new_text == text:
        return False
    path.write_text(new_text)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=os.environ.get("DBT_MANIFEST_PATH"),
        help="Path to dbt manifest.json (or set DBT_MANIFEST_PATH)",
    )
    args = parser.parse_args()

    if not args.manifest:
        print(
            "error: provide --manifest or set DBT_MANIFEST_PATH",
            file=sys.stderr,
        )
        sys.exit(1)

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"error: manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)

    cols_by_model = load_manifest(manifest_path)

    changed = 0
    skipped = 0
    for yml_path in sorted(CUBE_DIR.rglob("*.yml")):
        try:
            data = yaml.safe_load(yml_path.read_text())
        except yaml.YAMLError as e:
            print(f"  skip {yml_path.name}: YAML parse error — {e}", file=sys.stderr)
            skipped += 1
            continue

        cubes = (data or {}).get("cubes", [])
        if not cubes:
            skipped += 1
            continue

        sql_table = cubes[0].get("sql_table", "")
        if not sql_table:
            skipped += 1
            continue

        model_name = sql_table.split(".")[-1].strip()
        manifest_cols = cols_by_model.get(model_name, {})
        updates = direct_dims(cubes[0], manifest_cols)

        if not updates:
            print(f"  skip {yml_path.name}: no direct-column dims with dbt metadata")
            skipped += 1
            continue

        modified = patch_file(yml_path, updates)
        status = "updated" if modified else "unchanged"
        print(f"  {status} {yml_path.relative_to(CUBE_DIR.parent.parent.parent)}")
        if modified:
            changed += 1

    print(f"\n{changed} file(s) updated, {skipped} skipped.")


if __name__ == "__main__":
    main()
