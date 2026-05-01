# /// script
# requires-python = ">=3.13"
# dependencies = ["pyyaml>=6.0", "ruamel.yaml>=0.18"]
# ///

"""Sync dbt column descriptions and PII flags into Cube YAML files.

Two passes:

1. **Cube pass** — patches `description:` and `meta: {pii: true}` on dimensions
   that are direct column references (`name == sql`). Text-level surgery: only
   the target lines change; every other byte is written back unchanged.

2. **View pass** — updates `access_policy.excludes` on base-tier policy entries
   so that every PII dimension exposed by the view is excluded from the default
   access tier. Uses ruamel.yaml for round-trip editing of the list value.
   Existing excludes are preserved (union); items are only added, never removed.

Prerequisites:
    uv run scripts/dbt-manifest.py  # ensure manifest exists at target path

Usage:
    uv run scripts/sync-cube-descriptions.py --manifest <path-to-manifest.json>
    uv run scripts/sync-cube-descriptions.py  # uses DBT_MANIFEST_PATH env var
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from pathlib import Path

import yaml

CUBE_DIR = Path(__file__).parent.parent / "src" / "cube" / "model" / "cubes"
VIEW_DIR = Path(__file__).parent.parent / "src" / "cube" / "model" / "views"

DIM_ITEM_INDENT = 6  # "      - name: ..."
DIM_FIELD_INDENT = 8  # "        sql: ..."

# Groups whose access_policy entries see PII — don't add excludes to these.
PII_ACCESS_GROUPS = frozenset(
    {
        "cube-access-student-pii",
        "cube-access-staff-pii",
        "cube-access-staff-compensation",
        "cube-access-staff-benefits",
        "cube-access-staff-observations",
    }
)


# ── Manifest loading ──────────────────────────────────────────────────────────


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


# ── Cube pass (text-level) ────────────────────────────────────────────────────


def direct_dims(cube_data: dict, manifest_cols: dict[str, dict]) -> dict[str, dict]:
    """Return {dim_name: {description, pii}} for dims where name == sql."""
    updates: dict[str, dict] = {}
    for dim in cube_data.get("dimensions", []):
        name = dim["name"]
        sql = str(dim.get("sql", "")).strip()
        if name == sql and name in manifest_cols:
            updates[name] = manifest_cols[name]
    return updates


def patch_cube_file(path: Path, updates: dict[str, dict]) -> bool:
    """
    Insert/replace description and meta lines for each dim in updates.
    Returns True if the file was modified.

    Line-by-line state machine: tracks which dimension block the cursor is in.
    After emitting the `type:` line for an updatable dimension it skips any
    existing description/meta lines then injects the new values. Everything
    else is emitted byte-for-byte unchanged.

    Before running, filters updates to dimensions whose content actually
    differs from the current file (whitespace-normalised comparison). This
    makes the script idempotent even after a YAML formatter wraps long
    description strings to multi-line.
    """
    text = path.read_text()

    # Filter to dims where content differs (handles trunk multi-line reformats)
    try:
        file_data = yaml.safe_load(text)
        cubes = (file_data or {}).get("cubes", [])
        current: dict[str, dict] = {
            dim["name"]: {
                "description": " ".join(str(dim.get("description") or "").split()),
                "pii": bool((dim.get("meta") or {}).get("pii")),
                "has_meta_pii": "pii" in (dim.get("meta") or {}),
            }
            for dim in (cubes[0].get("dimensions", []) if cubes else [])
            if "name" in dim
        }
    except yaml.YAMLError:
        current = {}

    updates = {
        name: upd
        for name, upd in updates.items()
        if (
            " ".join(upd["description"].split())
            != current.get(name, {}).get("description", "")
            or upd["pii"] != current.get(name, {}).get("pii", False)
            or not current.get(name, {}).get("has_meta_pii", False)
        )
    }

    if not updates:
        return False

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

        # ── leaving updatable block (non-comment, non-blank, indent ≤ 6) ──
        if (
            current_dim is not None
            and indent <= DIM_ITEM_INDENT
            and stripped
            and not stripped.startswith("#")
        ):
            current_dim = None

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
                    i += 1
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

        result.append(line)
        i += 1

        if indent == DIM_FIELD_INDENT and stripped.startswith("type:"):
            update = updates[current_dim]
            pad = " " * DIM_FIELD_INDENT
            if update["description"]:
                desc = update["description"].replace('"', '\\"')
                result.append(f'{pad}description: "{desc}"\n')
            result.append(f"{pad}meta:\n")
            result.append(f"{pad}  pii: {'true' if update['pii'] else 'false'}\n")

    new_text = "".join(result)
    if new_text == text:
        return False
    path.write_text(new_text)
    return True


# ── View pass (ruamel.yaml round-trip) ───────────────────────────────────────


def build_cube_pii_index(
    cube_dir: Path, cols_by_model: dict[str, dict[str, dict]]
) -> dict[str, frozenset[str]]:
    """Return {cube_name: frozenset(pii_dim_names)} derived from the manifest."""
    index: dict[str, frozenset[str]] = {}
    for yml_path in sorted(cube_dir.rglob("*.yml")):
        try:
            data = yaml.safe_load(yml_path.read_text())
        except yaml.YAMLError:
            continue
        cubes = (data or {}).get("cubes", [])
        if not cubes:
            continue
        cube = cubes[0]
        cube_name = cube.get("name", "")
        sql_table = cube.get("sql_table", "")
        if not cube_name or not sql_table:
            continue
        model_name = sql_table.split(".")[-1].strip()
        manifest_cols = cols_by_model.get(model_name, {})
        pii_dims: set[str] = set()
        for dim in cube.get("dimensions", []):
            name = dim["name"]
            sql = str(dim.get("sql", "")).strip()
            if name == sql and manifest_cols.get(name, {}).get("pii"):
                pii_dims.add(name)
        index[cube_name] = frozenset(pii_dims)
    return index


def pii_excludes_for_view(
    view_data: dict, cube_pii: dict[str, frozenset[str]]
) -> list[str]:
    """Return sorted member names that should be excluded at the base tier."""
    excludes: set[str] = set()
    for join in view_data.get("cubes", []):
        cube_name = join.get("join_path", "").split(".")[-1]
        prefix = join.get("prefix", False)
        includes = join.get("includes", [])
        for dim_name in cube_pii.get(cube_name, frozenset()):
            if includes == "*" or dim_name in includes:
                member = f"{cube_name}_{dim_name}" if prefix else dim_name
                excludes.add(member)
    return sorted(excludes)


def patch_view_file(path: Path, new_pii_excludes: list[str]) -> bool:
    """
    Merge new_pii_excludes into the base-tier access_policy excludes list.
    Existing excludes are preserved (union — never removed).
    Returns True if the file was modified.
    """
    from ruamel.yaml import YAML as RuamelYAML
    from ruamel.yaml.comments import CommentedSeq

    ryaml = RuamelYAML()
    ryaml.preserve_quotes = True

    text = path.read_text()
    data = ryaml.load(text)

    views = (data or {}).get("views", [])
    if not views:
        return False

    modified = False
    for view in views:
        for policy in view.get("access_policy", []):
            if policy.get("group") in PII_ACCESS_GROUPS:
                continue
            ml = policy.get("member_level", {})
            existing = list(ml.get("excludes", []))
            merged = sorted(set(existing) | set(new_pii_excludes))
            if merged != sorted(existing):
                seq = CommentedSeq(merged)
                ml["excludes"] = seq
                modified = True

    if not modified:
        return False

    buf = io.StringIO()
    ryaml.dump(data, buf)
    new_text = buf.getvalue()
    if new_text == text:
        return False
    path.write_text(new_text)
    return True


# ── main ─────────────────────────────────────────────────────────────────────


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

    # ── Pass 1: cube files ────────────────────────────────────────────────
    print("Pass 1: cube dimensions")
    cube_changed = 0
    cube_skipped = 0
    for yml_path in sorted(CUBE_DIR.rglob("*.yml")):
        try:
            data = yaml.safe_load(yml_path.read_text())
        except yaml.YAMLError as e:
            print(f"  skip {yml_path.name}: YAML parse error — {e}", file=sys.stderr)
            cube_skipped += 1
            continue

        cubes = (data or {}).get("cubes", [])
        if not cubes:
            cube_skipped += 1
            continue

        sql_table = cubes[0].get("sql_table", "")
        if not sql_table:
            cube_skipped += 1
            continue

        model_name = sql_table.split(".")[-1].strip()
        manifest_cols = cols_by_model.get(model_name, {})
        updates = direct_dims(cubes[0], manifest_cols)

        if not updates:
            cube_skipped += 1
            continue

        modified = patch_cube_file(yml_path, updates)
        status = "updated" if modified else "unchanged"
        print(f"  {status} {yml_path.relative_to(CUBE_DIR.parent.parent.parent)}")
        if modified:
            cube_changed += 1

    print(f"  {cube_changed} file(s) updated, {cube_skipped} skipped.\n")

    # ── Pass 2: view files ────────────────────────────────────────────────
    print("Pass 2: view access_policy excludes")
    cube_pii = build_cube_pii_index(CUBE_DIR, cols_by_model)
    view_changed = 0
    view_skipped = 0
    for yml_path in sorted(VIEW_DIR.rglob("*.yml")):
        try:
            data = yaml.safe_load(yml_path.read_text())
        except yaml.YAMLError as e:
            print(f"  skip {yml_path.name}: YAML parse error — {e}", file=sys.stderr)
            view_skipped += 1
            continue

        views = (data or {}).get("views", [])
        if not views:
            view_skipped += 1
            continue

        new_pii_excludes = pii_excludes_for_view(views[0], cube_pii)
        modified = patch_view_file(yml_path, new_pii_excludes)
        status = "updated" if modified else "unchanged"
        print(f"  {status} {yml_path.relative_to(VIEW_DIR.parent.parent.parent)}")
        if modified:
            view_changed += 1

    print(f"  {view_changed} file(s) updated, {view_skipped} skipped.")


if __name__ == "__main__":
    main()
