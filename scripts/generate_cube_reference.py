# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "pyyaml>=6.0",
# ]
# ///

"""Generate the Cube semantic-layer field catalog.

Parses the Cube model YAML (src/cube/model/), resolves each view's exposed
members (flattening `extends:` chains and applying the `prefix:` naming rule),
and emits a single Markdown catalog page — one section per view. Only members a
view exposes are rendered; private cubes never surface.

No network or warehouse access on the default path. See --verify-against-meta
for the optional live /meta cross-check.

Usage:
    uv run scripts/generate_cube_reference.py            # regenerate the page
    uv run scripts/generate_cube_reference.py --check     # CI: fail if stale
    uv run scripts/generate_cube_reference.py --verify-against-meta

Design reference:
    docs/superpowers/specs/2026-07-17-cube-api-docs-design.md
"""

from __future__ import annotations

import argparse
import dataclasses
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = REPO_ROOT / "src/cube/model"
CUBES_DIR = MODEL_DIR / "cubes"
VIEWS_DIR = MODEL_DIR / "views"
DEFAULT_OUTPUT = REPO_ROOT / "docs/reference/cube-data-catalog.md"


@dataclasses.dataclass(frozen=True)
class CubeMember:
    """A single dimension or measure defined on a cube."""

    name: str
    kind: str  # "dimension" or "measure"
    type: str | None
    description: str | None
    primary_key: bool
    public: bool


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _member_from_def(defn: dict, kind: str) -> CubeMember:
    desc = defn.get("description")
    if desc is not None:
        desc = str(desc).strip() or None
    return CubeMember(
        name=defn["name"],
        kind=kind,
        type=defn.get("type"),
        description=desc,
        primary_key=bool(defn.get("primary_key", False)),
        public=bool(defn.get("public", False)),
    )


def parse_cubes(cubes_dir: Path) -> dict[str, dict[str, CubeMember]]:
    """Index every cube's members, flattening `extends:` chains.

    Returns {cube_name: {member_name: CubeMember}}. A cube with `extends:
    <parent>` inherits the parent's members; the child's own definitions win.
    """
    raw: dict[str, dict[str, CubeMember]] = {}
    extends: dict[str, str] = {}

    for path in sorted(cubes_dir.rglob("*.yml")):
        doc = _load_yaml(path)
        for cube in doc.get("cubes", []):
            name = cube["name"]
            if cube.get("extends"):
                extends[name] = cube["extends"]
            members: dict[str, CubeMember] = {}
            for defn in cube.get("dimensions", []):
                members[defn["name"]] = _member_from_def(defn, "dimension")
            for defn in cube.get("measures", []):
                members[defn["name"]] = _member_from_def(defn, "measure")
            raw[name] = members

    # Resolve extends. Iterate until stable to support extends-of-extends.
    resolved = {name: dict(members) for name, members in raw.items()}
    for _ in range(len(extends) + 1):
        for child, parent in extends.items():
            merged = dict(resolved.get(parent, {}))
            merged.update(raw.get(child, {}))
            resolved[child] = merged
    return resolved
