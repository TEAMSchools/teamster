# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "pyyaml>=6.0",
#   "pyjwt>=2.8",
#   "httpx>=0.27",
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
import os
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = REPO_ROOT / "src/cube/model"
CUBES_DIR = MODEL_DIR / "cubes"
VIEWS_DIR = MODEL_DIR / "views"
DEFAULT_OUTPUT = REPO_ROOT / "docs/reference/cube-data-catalog.md"


_ACRONYMS = {"pii": "PII"}


def friendly_name(slug: str) -> str:
    """Human title from a snake_case slug; known acronyms stay uppercase."""
    return " ".join(
        _ACRONYMS.get(w.lower(), w.capitalize()) for w in slug.replace("_", " ").split()
    )


def view_title(name: str) -> str:
    """Friendly view title; a trailing `_view` is dropped first."""
    base = name[:-5] if name.endswith("_view") else name
    return friendly_name(base)


def view_id(name: str) -> str:
    """Stable, collision-free heading id for a view (view names are unique)."""
    return "view-" + name.replace("_", "-")


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
    sensitive: bool = False


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
    domain: str = "other"

    @property
    def title(self) -> str:
        return view_title(self.name)

    @property
    def domain_title(self) -> str:
        return friendly_name(self.domain)


def _folder_map(view: dict) -> dict[str, str]:
    """{exposed_member_name: folder_name} from the view's meta.folders."""
    mapping: dict[str, str] = {}
    for folder in view.get("meta", {}).get("folders", []):
        for member in folder.get("members", []):
            mapping[member] = folder["name"]
    return mapping


# Curated sensitive member names (FERPA personal contact, DOB, demographics,
# and student identifiers). A per-member HINT for the "exposes PII" flag only —
# the authoritative access model is each view's access_policy and
# docs/guides/cube.md. Deliberately excludes directory-public names like
# `full_name` (the staff_directory roster is intentionally open), and matches
# bare exposed names only (a prefixed variant such as `staff_personal_email`
# would not match — see #4450 follow-up to source this from model metadata).
SENSITIVE_MEMBERS = frozenset(
    {
        "personal_email",
        "personal_cell_phone",
        "birth_date",
        "gender_identity",
        "race",
        "is_hispanic",
        "lea_student_identifier",
        "state_student_identifier",
    }
)


def _collect_row_level_members(filters: list, acc: list[str]) -> None:
    """Collect `member` names from row_level filters, recursing into or/and."""
    for flt in filters:
        member = flt.get("member")
        if member and member not in acc:
            acc.append(member)
        for group_key in ("and", "or"):
            nested = flt.get(group_key)
            if nested:
                _collect_row_level_members(nested, acc)


def derive_access(view: dict, members: list[ResolvedMember]) -> AccessSummary:
    groups: list[str] = []
    row_level: list[str] = []
    for policy in view.get("access_policy", []):
        group = policy.get("group")
        if group and group not in groups:
            groups.append(group)
        _collect_row_level_members(
            policy.get("row_level", {}).get("filters", []), row_level
        )
    exposes_pii = any(m.exposed_name in SENSITIVE_MEMBERS for m in members)
    return AccessSummary(
        groups=groups, row_level_members=row_level, exposes_pii=exposes_pii
    )


def resolve_view(
    view: dict, cubes: dict[str, dict[str, CubeMember]], domain: str = "other"
) -> ResolvedView:
    folders = _folder_map(view)
    members: list[ResolvedMember] = []

    for include in view.get("cubes", []):
        join_path = include["join_path"]
        prefix = bool(include.get("prefix", False))
        segment = join_path.split(".")[-1]  # cube whose members are included
        cube_members = cubes.get(segment, {})

        includes = include.get("includes", [])
        if includes == "*":
            # Never surface private helper members (e.g. `_sum_attendance_value`)
            # if a view ever wildcards a cube block.
            includes = [n for n in cube_members if not n.startswith("_")]

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
                    sensitive=exposed in SENSITIVE_MEMBERS,
                )
            )

    return ResolvedView(
        name=view["name"],
        description=(
            str(view["description"]).strip() if view.get("description") else None
        ),
        members=members,
        access=derive_access(view, members),
        domain=domain,
    )


def parse_views(
    views_dir: Path, cubes: dict[str, dict[str, CubeMember]]
) -> list[ResolvedView]:
    views: list[ResolvedView] = []
    for path in sorted(views_dir.rglob("*.yml")):
        rel = path.relative_to(views_dir)
        domain = rel.parts[0] if len(rel.parts) > 1 else "other"
        doc = _load_yaml(path)
        for view in doc.get("views", []):
            views.append(resolve_view(view, cubes, domain=domain))
    return sorted(views, key=lambda v: v.name)


BANNER = (
    "<!-- GENERATED FILE — do not edit by hand. Regenerate with:\n"
    "     uv run scripts/generate_cube_reference.py -->"
)

INTRO = (
    "Every analyst-facing Cube view and the fields it exposes. Only members a "
    "view publishes appear here — private cubes never surface. For how access is "
    "resolved and how to connect, see the [Cube guide](../guides/cube.md)."
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
    parts = [
        f"### {view.title} {{#{view_id(view.name)}}}",
        "",
        f"`{view.name}`",
        "",
    ]
    if view.description:
        parts += [_cell(view.description), ""]
    parts += ["#### Access", "", _access_block(view.access), ""]

    measures = [m for m in view.members if m.kind == "measure"]
    if measures:
        parts += ["#### Measures", "", _member_table(measures), ""]

    dims = [m for m in view.members if m.kind == "dimension"]
    if dims:
        parts += ["#### Dimensions", ""]
        for folder in _folder_order(view):
            in_folder = [m for m in dims if m.folder == folder]
            parts += [f"##### {folder}", "", _member_table(in_folder), ""]
    return "\n".join(parts).rstrip()


def render_domain_index(by_domain: dict[str, list[ResolvedView]]) -> str:
    return "## Views by domain"


def render_finder(views: list[ResolvedView]) -> str:
    return "## Find a field"


def render_page(views: list[ResolvedView]) -> str:
    by_domain: dict[str, list[ResolvedView]] = {}
    for v in sorted(views, key=lambda v: v.name):
        by_domain.setdefault(v.domain, []).append(v)

    sections: list[str] = ["# Cube data catalog", BANNER, INTRO]
    sections.append(render_domain_index(by_domain))
    sections.append(render_finder(views))
    for domain in sorted(by_domain):
        sections.append(f"## {friendly_name(domain)}")
        for v in by_domain[domain]:
            sections.append(render_view(v))
    return "\n\n".join(sections) + "\n"


def _normalize_table_row(stripped: str) -> str:
    cells = [c.strip() for c in stripped.strip("|").split("|")]
    norm = []
    for cell in cells:
        if re.fullmatch(r":?-+:?", cell):
            left = ":" if cell.startswith(":") else ""
            right = ":" if cell.endswith(":") else ""
            norm.append(f"{left}---{right}")
        else:
            norm.append(cell)
    return "| " + " | ".join(norm) + " |"


def _normalize(text: str) -> str:
    """Canonicalize markdown so prettier formatting is not a false diff.

    Table rows are re-joined with single-space cells; separator dash-runs
    collapse to `---` (alignment colons preserved). Prose paragraphs (runs of
    non-blank, non-table, non-heading lines) are unwrapped to one line and
    whitespace-collapsed, neutralizing the repo's `proseWrap: always` prettier
    setting. Headings and blank lines pass through as-is (rstripped).
    """
    out: list[str] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            out.append(re.sub(r"\s+", " ", " ".join(paragraph)).strip())
            paragraph.clear()

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            flush()
            out.append(_normalize_table_row(stripped))
        elif not stripped or stripped.startswith("#"):
            flush()
            out.append(line.rstrip())
        else:
            paragraph.append(stripped)
    flush()
    return "\n".join(out).strip() + "\n"


def check_stale(page: str, output: Path) -> int:
    if not output.exists():
        print(f"ERROR: {output} does not exist — run the generator.", file=sys.stderr)
        return 1
    if _normalize(page) != _normalize(output.read_text(encoding="utf-8")):
        print(
            "ERROR: cube data catalog is stale. Regenerate with:\n"
            "  uv run scripts/generate_cube_reference.py",
            file=sys.stderr,
        )
        return 1
    return 0


def _build_page(cubes_dir: Path, views_dir: Path) -> tuple[str, int]:
    cubes = parse_cubes(cubes_dir)
    views = parse_views(views_dir, cubes)
    return render_page(views), len(views)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cubes-dir", type=Path, default=CUBES_DIR)
    parser.add_argument("--views-dir", type=Path, default=VIEWS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="fail if stale")
    parser.add_argument(
        "--verify-against-meta",
        action="store_true",
        help="cross-check resolved members against the live /meta endpoint",
    )
    args = parser.parse_args(argv)

    page, n_views = _build_page(args.cubes_dir, args.views_dir)

    if args.verify_against_meta:
        return verify_against_meta(args.cubes_dir, args.views_dir)

    if args.check:
        return check_stale(page, args.output)

    args.output.write_text(page, encoding="utf-8")
    print(f"wrote {n_views} view sections to {args.output}")
    return 0


def fetch_meta(base_url: str, secret: str, email: str) -> dict:
    """GET {base_url}/meta as `email`, signing an HS256 JWT with `secret`.

    The identity must resolve to broad access or /meta hides views (access
    policies filter /meta). Raw token in Authorization — no `Bearer` prefix.
    """
    import httpx
    import jwt

    token = jwt.encode({"email": email}, secret, algorithm="HS256")
    resp = httpx.get(
        f"{base_url.rstrip('/')}/meta",
        headers={"Authorization": token},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


def meta_member_types(meta: dict) -> dict[str, dict[str, str]]:
    """{view_name: {bare_member_name: type}} from a /meta payload.

    /meta names members `<view>.<member>`; strip the leading view prefix.
    """
    result: dict[str, dict[str, str]] = {}
    for cube in meta.get("cubes", []):
        view = cube["name"]
        members: dict[str, str] = {}
        for kind in ("measures", "dimensions"):
            for m in cube.get(kind, []):
                bare = m["name"].split(".", 1)[1] if "." in m["name"] else m["name"]
                members[bare] = m.get("type")
        result[view] = members
    return result


def verify_against_meta(cubes_dir: Path, views_dir: Path, *, fetch=None) -> int:
    """Cross-check YAML-resolved members against the live /meta contract.

    Returns 0 on agreement, 1 on any discrepancy. `fetch` is injectable for
    tests; by default it reads CUBE_META_URL, CUBE_API_SECRET, CUBE_META_EMAIL.
    """
    if fetch is None:
        base_url = os.environ["CUBE_META_URL"]
        secret = os.environ["CUBE_API_SECRET"]
        email = os.environ["CUBE_META_EMAIL"]

        def _default_fetch() -> dict:
            return fetch_meta(base_url, secret, email)

        fetch = _default_fetch

    meta_types = meta_member_types(fetch())
    cubes = parse_cubes(cubes_dir)
    views = parse_views(views_dir, cubes)

    problems: list[str] = []
    for view in views:
        meta_members = meta_types.get(view.name)
        if meta_members is None:
            problems.append(f"{view.name}: absent from /meta (access or deploy?)")
            continue
        for m in view.members:
            if m.exposed_name not in meta_members:
                problems.append(
                    f"{view.name}.{m.exposed_name}: resolved from YAML but absent "
                    f"from /meta"
                )

    for problem in problems:
        print(f"META MISMATCH: {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"/meta verification passed for {len(views)} views")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
