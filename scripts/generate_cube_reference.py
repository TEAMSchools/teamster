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


# Known sensitive member names (FERPA direct/indirect identifiers). Used only
# to flag "exposes PII" in the access summary; the authoritative access model
# is each view's access_policy and docs/guides/cube.md.
SENSITIVE_MEMBERS = frozenset(
    {
        "personal_email",
        "personal_cell_phone",
        "birth_date",
        "gender_identity",
        "race",
        "is_hispanic",
        "full_name",
        "lea_student_identifier",
        "state_student_identifier",
    }
)


def derive_access(view: dict, members: list[ResolvedMember]) -> AccessSummary:
    groups: list[str] = []
    row_level: list[str] = []
    for policy in view.get("access_policy", []):
        group = policy.get("group")
        if group and group not in groups:
            groups.append(group)
        for flt in policy.get("row_level", {}).get("filters", []):
            member = flt.get("member")
            if member and member not in row_level:
                row_level.append(member)
    exposes_pii = any(m.exposed_name in SENSITIVE_MEMBERS for m in members)
    return AccessSummary(
        groups=groups, row_level_members=row_level, exposes_pii=exposes_pii
    )


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
        access=derive_access(view, members),
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


BANNER = (
    "<!-- GENERATED FILE — do not edit by hand. Regenerate with:\n"
    "     uv run scripts/generate_cube_reference.py -->"
)

INTRO = (
    "Every analyst-facing Cube view and the fields it exposes. Only members a "
    "view publishes appear here — private cubes never surface. For auth, query "
    "format, and worked examples see the "
    "[Cube API guide](../guides/cube-api.md)."
)

PLACEHOLDER = "_No description._"


def _cell(value: str | None) -> str:
    """Escape a table cell (pipes, newlines collapsed)."""
    text = (value or "").replace("\n", " ").replace("|", "\\|")
    return re.sub(r"\s+", " ", text).strip()


def _member_table(members: list[ResolvedMember]) -> str:
    lines = ["| Name | Type | Description |", "| --- | --- | --- |"]
    for m in sorted(members, key=lambda x: x.exposed_name):
        desc = _cell(m.description) if m.description else PLACEHOLDER
        lines.append(f"| `{m.exposed_name}` | {_cell(m.type)} | {desc} |")
    return "\n".join(lines)


def _access_block(access: AccessSummary) -> str:
    if not access.groups:
        groups = "None — default-deny (no reader group)."
    else:
        groups = ", ".join(f"`{g}`" for g in access.groups)
    lines = [f"**Reader groups:** {groups}"]
    if access.row_level_members:
        scoped = ", ".join(f"`{m}`" for m in access.row_level_members)
        lines.append(f"**Row-level scoping on:** {scoped}")
    if access.exposes_pii:
        lines.append(
            "**Contains sensitive / PII fields** — see access policy in "
            "[cube.md](../guides/cube.md#admin-setup)."
        )
    return "\n\n".join(lines)


def _folder_order(view: ResolvedView) -> list[str]:
    """Folder names in first-seen order, with Other last."""
    order: list[str] = []
    for m in view.members:
        if m.kind == "dimension" and m.folder and m.folder not in order:
            order.append(m.folder)
    if OTHER_FOLDER in order:
        order.remove(OTHER_FOLDER)
        order.append(OTHER_FOLDER)
    return order


def render_view(view: ResolvedView) -> str:
    parts = [f"## {view.name}", ""]
    if view.description:
        parts += [_cell(view.description), ""]
    parts += ["### Access", "", _access_block(view.access), ""]

    measures = [m for m in view.members if m.kind == "measure"]
    if measures:
        parts += ["### Measures", "", _member_table(measures), ""]

    dims = [m for m in view.members if m.kind == "dimension"]
    if dims:
        parts += ["### Dimensions", ""]
        for folder in _folder_order(view):
            in_folder = [m for m in dims if m.folder == folder]
            parts += [f"#### {folder}", "", _member_table(in_folder), ""]
    return "\n".join(parts).rstrip()


def render_page(views: list[ResolvedView]) -> str:
    body = "\n\n".join(
        ["# Cube data catalog", BANNER, INTRO, *(render_view(v) for v in views)]
    )
    return body + "\n"
