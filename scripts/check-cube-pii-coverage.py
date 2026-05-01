# /// script
# requires-python = ">=3.13"
# dependencies = ["pyyaml>=6.0"]
# ///

"""Verify Cube YAML conventions and PII access_policy coverage.

Three checks run against committed cube and view YAML files:

1. **Name-sql mismatch** — dimensions where `sql` is a plain column identifier
   but `name` differs. Rename in dbt or use `name == sql`.

2. **Missing PII indicator** — every dimension must have `meta: {pii: true}`
   or `meta: {pii: false}` explicitly set. Run sync-cube-descriptions.py to
   populate direct dims; set manually for expression dims.

3. **View PII coverage** — every PII-flagged cube dimension exposed by a view
   must appear in the base-tier access_policy excludes list.

Exits 1 if any violation is found.

Usage (CI):
    uv run scripts/check-cube-pii-coverage.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

_PLAIN_ID = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

CUBE_DIR = Path(__file__).parent.parent / "src" / "cube" / "model" / "cubes"
VIEW_DIR = Path(__file__).parent.parent / "src" / "cube" / "model" / "views"

PII_ACCESS_GROUPS = frozenset(
    {
        "cube-access-student-pii",
        "cube-access-staff-pii",
        "cube-access-staff-compensation",
        "cube-access-staff-benefits",
        "cube-access-staff-observations",
    }
)


def check_cube_file(path: Path) -> list[str]:
    """Return violation strings for cube YAML convention issues."""
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        return [f"{path.name}: YAML parse error — {e}"]

    cubes = (data or {}).get("cubes", [])
    if not cubes:
        return []

    cube = cubes[0]
    cube_name = cube.get("name", path.stem)
    violations: list[str] = []

    for dim in cube.get("dimensions", []):
        name = dim.get("name", "")
        sql = str(dim.get("sql", "")).strip()
        ref = f"{cube_name}.{name}"

        if _PLAIN_ID.match(sql) and name != sql:
            violations.append(
                f"{ref}: name '{name}' doesn't match sql '{sql}'"
                " — rename in dbt or use name == sql"
            )

        if "pii" not in (dim.get("meta") or {}):
            violations.append(f"{ref}: missing meta.pii (set to true or false)")

    return violations


def build_cube_pii_index() -> dict[str, frozenset[str]]:
    """Return {cube_name: frozenset(pii_dim_names)} from committed cube YAML."""
    index: dict[str, frozenset[str]] = {}
    for yml_path in sorted(CUBE_DIR.rglob("*.yml")):
        try:
            data = yaml.safe_load(yml_path.read_text())
        except yaml.YAMLError:
            continue
        cubes = (data or {}).get("cubes", [])
        if not cubes:
            continue
        cube = cubes[0]
        cube_name = cube.get("name", "")
        if not cube_name:
            continue
        pii_dims: set[str] = set()
        for dim in cube.get("dimensions", []):
            meta = dim.get("meta") or {}
            if meta.get("pii"):
                pii_dims.add(dim["name"])
        index[cube_name] = frozenset(pii_dims)
    return index


def check_view(path: Path, cube_pii: dict[str, frozenset[str]]) -> list[str]:
    """
    Return violation strings for any PII dimension exposed without exclusion.
    A dimension is a violation if it appears in a base-tier policy's reachable
    members but is not listed in that policy's excludes.
    """
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        return [f"{path.name}: YAML parse error — {e}"]

    views = (data or {}).get("views", [])
    if not views:
        return []

    view = views[0]
    view_name = view.get("name", path.stem)

    # Collect PII members exposed by this view
    exposed_pii: set[str] = set()
    for join in view.get("cubes", []):
        cube_name = join.get("join_path", "").split(".")[-1]
        prefix = join.get("prefix", False)
        includes = join.get("includes", [])
        for dim_name in cube_pii.get(cube_name, frozenset()):
            if includes == "*" or dim_name in includes:
                member = f"{cube_name}_{dim_name}" if prefix else dim_name
                exposed_pii.add(member)

    if not exposed_pii:
        return []

    # Collect what each base-tier policy entry actually excludes
    violations: list[str] = []
    for policy in view.get("access_policy", []):
        group = policy.get("group", "")
        if group in PII_ACCESS_GROUPS:
            continue
        excluded = set(policy.get("member_level", {}).get("excludes") or [])
        uncovered = exposed_pii - excluded
        for member in sorted(uncovered):
            violations.append(
                f"{view_name}: '{member}' is PII but not excluded from group '{group}'"
            )

    return violations


def main() -> None:
    all_violations: list[str] = []

    for yml_path in sorted(CUBE_DIR.rglob("*.yml")):
        all_violations.extend(check_cube_file(yml_path))

    cube_pii = build_cube_pii_index()
    for yml_path in sorted(VIEW_DIR.rglob("*.yml")):
        all_violations.extend(check_view(yml_path, cube_pii))

    if all_violations:
        print("Cube model violations found:\n", file=sys.stderr)
        for v in all_violations:
            print(f"  {v}", file=sys.stderr)
        print(
            "\nRun scripts/sync-cube-descriptions.py to fix direct dims,"
            " or update cube YAML manually for expression dims.",
            file=sys.stderr,
        )
        sys.exit(1)

    pii_count = sum(len(v) for v in cube_pii.values())
    print(
        f"OK — {pii_count} PII dimension(s) across {len(cube_pii)} cube(s), all covered."
    )


if __name__ == "__main__":
    main()
