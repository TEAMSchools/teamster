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


OTHER_FOLDER = "Other"


@dataclasses.dataclass(frozen=True)
class ResolvedMember:
    exposed_name: str
    kind: str
    type: str | None
    description: str | None
    folder: str
    source: str


@dataclasses.dataclass
class AccessSummary:
    groups: list[str] = dataclasses.field(default_factory=list)
    row_level_members: list[str] = dataclasses.field(default_factory=list)
    exposes_pii: bool = False


@dataclasses.dataclass
class ResolvedView:
    name: str
    description: str | None
    members: list[ResolvedMember]
    access: AccessSummary


def _folder_map(view: dict) -> dict[str, str]:
    """{exposed_member_name: folder_name} from the view's meta.folders."""
    mapping: dict[str, str] = {}
    for folder in view.get("meta", {}).get("folders", []):
        for member in folder.get("members", []):
            mapping[member] = folder["name"]
    return mapping


def resolve_view(view: dict, cubes: dict[str, dict[str, CubeMember]]) -> ResolvedView:
    folders = _folder_map(view)
    members: list[ResolvedMember] = []

    for include in view.get("cubes", []):
        join_path = include["join_path"]
        prefix = bool(include.get("prefix", False))
        segment = join_path.split(".")[-1]  # cube whose members are included
        cube_members = cubes.get(segment, {})

        includes = include.get("includes", [])
        if includes == "*":
            includes = list(cube_members)

        for raw_member in includes:
            member_name = (
                raw_member["name"] if isinstance(raw_member, dict) else raw_member
            )
            info = cube_members.get(member_name)
            if info is None:
                print(
                    f"WARNING: {view['name']}: {segment}.{member_name} not found "
                    f"on cube (check extends/join_path)",
                    file=sys.stderr,
                )
                continue
            exposed = f"{segment}_{member_name}" if prefix else member_name
            folder = (
                "" if info.kind == "measure" else folders.get(exposed, OTHER_FOLDER)
            )
            members.append(
                ResolvedMember(
                    exposed_name=exposed,
                    kind=info.kind,
                    type=info.type,
                    description=info.description,
                    folder=folder,
                    source=f"{segment}.{member_name}",
                )
            )

    return ResolvedView(
        name=view["name"],
        description=(
            str(view["description"]).strip() if view.get("description") else None
        ),
        members=members,
        access=AccessSummary(),
    )


def parse_views(
    views_dir: Path, cubes: dict[str, dict[str, CubeMember]]
) -> list[ResolvedView]:
    views: list[ResolvedView] = []
    for path in sorted(views_dir.rglob("*.yml")):
        doc = _load_yaml(path)
        for view in doc.get("views", []):
            views.append(resolve_view(view, cubes))
    return sorted(views, key=lambda v: v.name)
