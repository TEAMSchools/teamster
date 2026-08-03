# Cube API Reference and Field Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an auto-generated Cube field catalog plus a hand-written API
guide, under the existing MkDocs site, that documents exactly the members Cube
views expose — and a CI check that keeps the catalog from ever going stale.

**Architecture:** A standalone PEP-723 Python generator parses the Cube model
YAML (`src/cube/model/`), resolves each view's exposed members (applying the
`extends:` and `prefix:` rules), and renders one Markdown catalog page. A
separate GitHub Actions workflow re-runs it in `--check` mode on PRs touching
`src/cube/**` and fails if the committed catalog is out of date. The narrative
API guide is hand-written and stable.

**Tech Stack:** Python 3.13, `pyyaml` (parse), `pyjwt` + `httpx` (optional
`/meta` verification), `pytest` (golden-file tests), MkDocs Material (site),
GitHub Actions (CI).

## Global Constraints

- **Run Python only via `uv run`** — never bare `python`/`python3`.
- **Generator is a standalone PEP-723 script** under `scripts/`, mirroring
  `scripts/generate_marts_reference.py`: inline `# /// script` deps, no entry in
  `pyproject.toml`, no `scripts/__init__.py`.
- **Views are the only documented surface.** The generator renders only members
  a view's `includes:` exposes. Never emit anything from a cube directly; every
  cube is `public: false`.
- **Descriptions live on cubes, not views.** Missing descriptions render a
  visible placeholder; filling them is out of scope (tracked in
  [#4450](https://github.com/TEAMSchools/teamster/issues/4450)).
- **Committed generated output is prettier-padded.** The pre-commit formatter
  pads Markdown tables after generation, so the working tree shows table-padding
  churn between run and commit — expected. The CI `--check` compares
  **normalized** output so padding is not a false positive.
- **Markdown rules** (fire at pre-push/CI, not the pre-commit `fmt` hook): every
  fenced block needs a language (MD040; use `text` when none applies); headings
  increment by one level (MD001); no standalone `**bold**` pseudo-headings
  (MD036); ordered lists broken by fences use `1.` for every item (MD029). Lint
  every edited `.md` with
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <file> </dev/null`
  before committing.
- **Adding an MkDocs page requires a `nav:` entry** in `mkdocs.yml` (nav is
  explicit).

---

## File Structure

| Path                                                 | Responsibility                                                                               |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `scripts/generate_cube_reference.py`                 | Parse model YAML → resolve view members → render catalog; `--check`, `--verify-against-meta` |
| `tests/scripts/test_generate_cube_reference.py`      | Golden-file + unit tests for the generator                                                   |
| `tests/scripts/fixtures/cube_ref_sample/cubes/*.yml` | Fixture cubes (measures, dims, missing desc, `extends`)                                      |
| `tests/scripts/fixtures/cube_ref_sample/views/*.yml` | Fixture view (prefix true/false, folders, access policy)                                     |
| `docs/reference/cube-data-catalog.md`                | GENERATED catalog page (committed)                                                           |
| `docs/guides/cube-api.md`                            | Hand-written API/query guide                                                                 |
| `docs/guides/cube.md`                                | Cross-links to the two new pages                                                             |
| `mkdocs.yml`                                         | Nav entries + `toc.integrate` feature                                                        |
| `docs/CLAUDE.md`                                     | Documents the generator + freshness check                                                    |
| `scripts/CLAUDE.md`                                  | Script-catalog + prerequisites entry                                                         |
| `.github/workflows/cube-docs-check.yaml`             | CI freshness check                                                                           |

---

## Task 1: Generator scaffold + parse cubes with `extends` resolution

**Files:**

- Create: `scripts/generate_cube_reference.py`
- Create: `tests/scripts/test_generate_cube_reference.py`
- Create: `tests/scripts/fixtures/cube_ref_sample/cubes/sample_fact.yml`
- Create: `tests/scripts/fixtures/cube_ref_sample/cubes/sample_dim.yml`
- Create: `tests/scripts/fixtures/cube_ref_sample/cubes/sample_base.yml`
- Create: `tests/scripts/fixtures/cube_ref_sample/cubes/sample_alias.yml`

**Interfaces:**

- Produces: `CubeMember` dataclass with fields `name: str`, `kind: str`
  (`"dimension"`/`"measure"`), `type: str | None`, `description: str | None`,
  `primary_key: bool`, `public: bool`.
  `parse_cubes(cubes_dir: Path) -> dict[str, dict[str, CubeMember]]` returns
  `{cube_name: {member_name: CubeMember}}` with `extends:` chains already
  flattened.

- [ ] **Step 1: Create the fixture cubes**

`tests/scripts/fixtures/cube_ref_sample/cubes/sample_fact.yml`:

```yaml
cubes:
  - name: sample_fact
    public: false
    sql_table: kipptaf_marts.fct_sample
    dimensions:
      - name: grade_level
        description: Student grade level.
        sql: grade_level
        type: number
        public: true
      - name: no_desc_dim
        sql: no_desc_dim
        type: string
        public: true
    measures:
      - name: count_rows
        description: Row count.
        type: count
        public: true
```

`tests/scripts/fixtures/cube_ref_sample/cubes/sample_dim.yml`:

```yaml
cubes:
  - name: sample_dim
    public: false
    sql_table: kipptaf_marts.dim_sample
    dimensions:
      - name: region_name
        description: Region name.
        sql: region_name
        type: string
        public: true
```

`tests/scripts/fixtures/cube_ref_sample/cubes/sample_base.yml`:

```yaml
cubes:
  - name: sample_base
    public: false
    sql_table: kipptaf_marts.dim_base
    dimensions:
      - name: base_key
        description: Base key.
        sql: base_key
        type: string
        primary_key: true
        public: true
```

`tests/scripts/fixtures/cube_ref_sample/cubes/sample_alias.yml`:

```yaml
cubes:
  - name: sample_alias
    extends: sample_base
    public: false
```

- [ ] **Step 2: Write the failing test**

Create `tests/scripts/test_generate_cube_reference.py`:

```python
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

FIXTURE_DIR = Path(__file__).parent / "fixtures/cube_ref_sample"
SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts/generate_cube_reference.py"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "generate_cube_reference", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_cube_reference"] = module
    spec.loader.exec_module(module)
    return module


gen = _load_module()


def test_parse_cubes_indexes_members_and_kinds() -> None:
    cubes = gen.parse_cubes(FIXTURE_DIR / "cubes")

    fact = cubes["sample_fact"]
    assert fact["count_rows"].kind == "measure"
    assert fact["grade_level"].kind == "dimension"
    assert fact["grade_level"].type == "number"
    assert fact["grade_level"].description == "Student grade level."
    # missing description is preserved as None (not the empty string)
    assert fact["no_desc_dim"].description is None


def test_parse_cubes_flattens_extends() -> None:
    cubes = gen.parse_cubes(FIXTURE_DIR / "cubes")

    # sample_alias extends sample_base and defines no members of its own, so it
    # inherits base_key with its description and primary_key flag.
    alias = cubes["sample_alias"]
    assert "base_key" in alias
    assert alias["base_key"].description == "Base key."
    assert alias["base_key"].primary_key is True
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/scripts/test_generate_cube_reference.py -v` Expected:
FAIL — `ModuleNotFoundError` / file not found for the script.

- [ ] **Step 4: Write the generator scaffold + `parse_cubes`**

Create `scripts/generate_cube_reference.py`:

```python
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
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/scripts/test_generate_cube_reference.py -v` Expected:
PASS (both tests).

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_cube_reference.py tests/scripts/test_generate_cube_reference.py tests/scripts/fixtures/cube_ref_sample/cubes
git commit -m "feat(cube-docs): parse cubes with extends resolution

Refs #4438"
```

---

## Task 2: Parse views + resolve exposed members

**Files:**

- Modify: `scripts/generate_cube_reference.py` (add resolution functions)
- Modify: `tests/scripts/test_generate_cube_reference.py` (add tests)
- Create: `tests/scripts/fixtures/cube_ref_sample/views/sample_view.yml`

**Interfaces:**

- Consumes: `parse_cubes` from Task 1.
- Produces: `ResolvedMember` dataclass with `exposed_name: str`, `kind: str`,
  `type: str | None`, `description: str | None`, `folder: str`, `source: str`
  (e.g. `"sample_fact.grade_level"`).
  `resolve_view(view: dict, cubes: dict) -> ResolvedView`, where `ResolvedView`
  has `name: str`, `description: str | None`, `members: list[ResolvedMember]`,
  and `access: AccessSummary` (populated in Task 3; default-constructed here).
  `parse_views(views_dir, cubes) -> list[ResolvedView]`.

- [ ] **Step 1: Create the fixture view**

`tests/scripts/fixtures/cube_ref_sample/views/sample_view.yml`:

```yaml
views:
  - name: sample_view
    description: A sample view for tests.
    cubes:
      - join_path: sample_fact
        includes:
          - count_rows
          - grade_level
          - no_desc_dim
      - join_path: sample_fact.sample_dim
        prefix: true
        includes:
          - region_name
      - join_path: sample_fact.sample_alias
        prefix: false
        includes:
          - base_key
    meta:
      folders:
        - name: Sample
          members:
            - grade_level
            - no_desc_dim
        - name: Region
          members:
            - sample_dim_region_name
    access_policy:
      - group: sample-network
        member_level:
          includes: "*"
      - group: sample-region
        member_level:
          includes: "*"
        row_level:
          filters:
            - member: sample_dim_region_name
              operator: equals
              values: ["{ securityContext.region_key }"]
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/scripts/test_generate_cube_reference.py`:

```python
def _resolved_view(name: str = "sample_view"):
    cubes = gen.parse_cubes(FIXTURE_DIR / "cubes")
    views = gen.parse_views(FIXTURE_DIR / "views", cubes)
    return next(v for v in views if v.name == name)


def test_resolve_view_applies_prefix_rule() -> None:
    view = _resolved_view()
    by_name = {m.exposed_name: m for m in view.members}

    # prefix: false -> bare member names
    assert "grade_level" in by_name
    assert "count_rows" in by_name
    assert "base_key" in by_name  # from sample_alias (extends sample_base)
    # prefix: true -> <last-join_path-segment>_<member>
    assert "sample_dim_region_name" in by_name
    assert by_name["sample_dim_region_name"].description == "Region name."


def test_resolve_view_classifies_and_types_members() -> None:
    view = _resolved_view()
    by_name = {m.exposed_name: m for m in view.members}

    assert by_name["count_rows"].kind == "measure"
    assert by_name["grade_level"].kind == "dimension"
    assert by_name["grade_level"].type == "number"
    assert by_name["no_desc_dim"].description is None
    assert by_name["grade_level"].source == "sample_fact.grade_level"


def test_resolve_view_assigns_folders_with_other_fallback() -> None:
    view = _resolved_view()
    by_name = {m.exposed_name: m for m in view.members}

    assert by_name["grade_level"].folder == "Sample"
    assert by_name["sample_dim_region_name"].folder == "Region"
    # base_key is exposed but listed in no meta folder -> "Other"
    assert by_name["base_key"].folder == "Other"
    # measures are never folder-grouped
    assert by_name["count_rows"].folder == ""
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/scripts/test_generate_cube_reference.py -v` Expected:
FAIL — `AttributeError: module ... has no attribute 'parse_views'`.

- [ ] **Step 4: Implement view resolution**

Add to `scripts/generate_cube_reference.py` (after `parse_cubes`):

```python
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
            member_name = raw_member["name"] if isinstance(raw_member, dict) else raw_member
            info = cube_members.get(member_name)
            if info is None:
                print(
                    f"WARNING: {view['name']}: {segment}.{member_name} not found "
                    f"on cube (check extends/join_path)",
                    file=sys.stderr,
                )
                continue
            exposed = f"{segment}_{member_name}" if prefix else member_name
            folder = "" if info.kind == "measure" else folders.get(exposed, OTHER_FOLDER)
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
        description=(str(view["description"]).strip() if view.get("description") else None),
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
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/scripts/test_generate_cube_reference.py -v` Expected:
PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_cube_reference.py tests/scripts/test_generate_cube_reference.py tests/scripts/fixtures/cube_ref_sample/views
git commit -m "feat(cube-docs): resolve view members with prefix + folder rules

Refs #4438"
```

---

## Task 3: Derive the per-view access summary

**Files:**

- Modify: `scripts/generate_cube_reference.py` (add `derive_access`, call it in
  `resolve_view`)
- Modify: `tests/scripts/test_generate_cube_reference.py` (add tests)

**Interfaces:**

- Consumes: `AccessSummary`, `ResolvedView` from Task 2.
- Produces:
  `derive_access(view: dict, members: list[ResolvedMember]) -> AccessSummary`.
  `resolve_view` now sets `access=derive_access(...)`.

- [ ] **Step 1: Write the failing test**

Append to the test file:

```python
def test_derive_access_reads_groups_and_row_level() -> None:
    view = _resolved_view()
    access = view.access

    assert access.groups == ["sample-network", "sample-region"]
    assert access.row_level_members == ["sample_dim_region_name"]
    # no sensitive members in the fixture
    assert access.exposes_pii is False
```

- [ ] **Step 2: Run to verify failure**

Run:
`uv run pytest tests/scripts/test_generate_cube_reference.py::test_derive_access_reads_groups_and_row_level -v`
Expected: FAIL — `access.groups` is `[]` (default), not the policy groups.

- [ ] **Step 3: Implement `derive_access`**

Add to `scripts/generate_cube_reference.py` (before `resolve_view`):

```python
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
```

Then change the `return ResolvedView(...)` line in `resolve_view` so
`access=derive_access(view, members)` instead of `access=AccessSummary()`:

```python
    return ResolvedView(
        name=view["name"],
        description=(str(view["description"]).strip() if view.get("description") else None),
        members=members,
        access=derive_access(view, members),
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/scripts/test_generate_cube_reference.py -v` Expected:
PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_cube_reference.py tests/scripts/test_generate_cube_reference.py
git commit -m "feat(cube-docs): derive per-view access summary from access_policy

Refs #4438"
```

---

## Task 4: Render the catalog Markdown

**Files:**

- Modify: `scripts/generate_cube_reference.py` (add render functions + `BANNER`)
- Modify: `tests/scripts/test_generate_cube_reference.py` (add tests)

**Interfaces:**

- Consumes: `ResolvedView`, `ResolvedMember` from Tasks 2-3.
- Produces: `BANNER: str`; `render_view(view: ResolvedView) -> str`;
  `render_page(views: list[ResolvedView]) -> str`.

- [ ] **Step 1: Write the failing tests**

Append to the test file:

```python
def test_render_page_has_banner_and_one_h2_per_view() -> None:
    cubes = gen.parse_cubes(FIXTURE_DIR / "cubes")
    views = gen.parse_views(FIXTURE_DIR / "views", cubes)
    page = gen.render_page(views)

    assert page.startswith("# Cube data catalog\n")
    assert gen.BANNER in page
    assert page.count("\n## ") == 1
    assert "## sample_view" in page


def test_render_view_tables_and_placeholder() -> None:
    view = _resolved_view()
    block = gen.render_view(view)

    # measures section + a measure row
    assert "### Measures" in block
    assert "| `count_rows` | count | Row count. |" in block
    # dimensions grouped by folder heading
    assert "#### Sample" in block
    assert "#### Region" in block
    assert "#### Other" in block
    assert "| `grade_level` | number | Student grade level. |" in block
    # missing description -> visible placeholder, not blank
    assert "| `no_desc_dim` | string | _No description._ |" in block
    # access summary line
    assert "sample-network" in block
    assert "sample-region" in block
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/scripts/test_generate_cube_reference.py -v` Expected:
FAIL — no `render_page` / `BANNER`.

- [ ] **Step 3: Implement rendering**

Add to `scripts/generate_cube_reference.py`:

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/scripts/test_generate_cube_reference.py -v` Expected:
PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_cube_reference.py tests/scripts/test_generate_cube_reference.py
git commit -m "feat(cube-docs): render catalog markdown with folders + access

Refs #4438"
```

---

## Task 5: `main`, `--output`, and `--check` (padding-tolerant)

**Files:**

- Modify: `scripts/generate_cube_reference.py` (add `_normalize`, `check_stale`,
  `main`, `__main__`)
- Modify: `tests/scripts/test_generate_cube_reference.py` (add tests)

**Interfaces:**

- Consumes: `render_page`, `parse_cubes`, `parse_views`.
- Produces: `_normalize(text: str) -> str`;
  `check_stale(page: str, output: Path) -> int`;
  `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write the failing tests**

Append to the test file:

```python
def test_normalize_neutralizes_table_padding() -> None:
    compact = "| Name | Type |\n| --- | --- |\n| `a` | number |\n"
    padded = "| Name  | Type   |\n| ----- | ------ |\n| `a`   | number |\n"
    assert gen._normalize(compact) == gen._normalize(padded)


def test_check_stale_passes_on_padding_only_diff(tmp_path) -> None:
    page = "| Name | Type |\n| --- | --- |\n| `a` | number |\n"
    padded_file = tmp_path / "out.md"
    padded_file.write_text(
        "| Name  | Type   |\n| ----- | ------ |\n| `a`   | number |\n",
        encoding="utf-8",
    )
    assert gen.check_stale(page, padded_file) == 0


def test_check_stale_fails_on_content_diff(tmp_path) -> None:
    page = "| Name | Type |\n| --- | --- |\n| `a` | number |\n"
    out = tmp_path / "out.md"
    out.write_text("| Name | Type |\n| --- | --- |\n| `b` | number |\n", encoding="utf-8")
    assert gen.check_stale(page, out) == 1


def test_main_writes_output(tmp_path) -> None:
    out = tmp_path / "catalog.md"
    rc = gen.main(
        [
            "--cubes-dir", str(FIXTURE_DIR / "cubes"),
            "--views-dir", str(FIXTURE_DIR / "views"),
            "--output", str(out),
        ]
    )
    assert rc == 0
    assert "## sample_view" in out.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/scripts/test_generate_cube_reference.py -v` Expected:
FAIL — no `_normalize` / `check_stale` / `main` arg support.

- [ ] **Step 3: Implement `main` + `--check`**

Add to `scripts/generate_cube_reference.py`:

```python
def _normalize(text: str) -> str:
    """Canonicalize markdown so prettier table-padding is not a false diff.

    Table rows are re-joined with single-space cells; separator dash-runs
    collapse to `---` (alignment colons preserved); other lines are rstripped.
    """
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            norm = []
            for cell in cells:
                if re.fullmatch(r":?-+:?", cell):
                    left = ":" if cell.startswith(":") else ""
                    right = ":" if cell.endswith(":") else ""
                    norm.append(f"{left}---{right}")
                else:
                    norm.append(cell)
            out.append("| " + " | ".join(norm) + " |")
        else:
            out.append(line.rstrip())
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


if __name__ == "__main__":
    raise SystemExit(main())
```

Note: `verify_against_meta` is implemented in Task 7. Until then, add a
temporary stub at the end of the module so the script imports cleanly:

```python
def verify_against_meta(cubes_dir: Path, views_dir: Path) -> int:
    print("ERROR: --verify-against-meta not implemented yet", file=sys.stderr)
    return 2
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/scripts/test_generate_cube_reference.py -v` Expected:
PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_cube_reference.py tests/scripts/test_generate_cube_reference.py
git commit -m "feat(cube-docs): add main, --output, padding-tolerant --check

Refs #4438"
```

---

## Task 6: Generate the real catalog + wire MkDocs nav

**Files:**

- Create (generated): `docs/reference/cube-data-catalog.md`
- Modify: `mkdocs.yml` (nav entry + `toc.integrate` feature)

**Interfaces:** none (integration task).

- [ ] **Step 1: Generate the catalog against the real model**

Run: `uv run scripts/generate_cube_reference.py` Expected:
`wrote 5 view sections to .../docs/reference/cube-data-catalog.md` (the five
views: `staff_directory`, `staff_pii`, `student_assessment_scores_view`,
`student_attendance_view`, `student_enrollments_view`).

- [ ] **Step 2: Sanity-check the output**

Run: `grep -c '^## ' docs/reference/cube-data-catalog.md` Expected: `5`

Run: `grep -c '_No description._' docs/reference/cube-data-catalog.md` Expected:
`9` (matches the gap enumerated in #4450; the placeholder count is a useful
regression signal, not a hard requirement).

- [ ] **Step 3: Add the nav entry and `toc.integrate`**

In `mkdocs.yml`, add `toc.integrate` to `theme.features` (immediately after
`toc.follow`):

```yaml
- toc.follow
- toc.integrate
```

In `mkdocs.yml` `nav:`, under the `Reference:` list, add the catalog after
`Marts Data Models:` (keep alphabetical-ish grouping with the other data
references):

```yaml
- Marts Data Models: reference/marts-data-models.md
- Cube Data Catalog: reference/cube-data-catalog.md
```

- [ ] **Step 4: Build the site to confirm it renders**

Run: `uv run --group docs mkdocs build --strict 2>&1 | tail -20` Expected: build
succeeds. If `--strict` fails only on pre-existing warnings unrelated to the new
page, re-run without `--strict` and confirm the new page builds; note any
pre-existing warning rather than "fixing" it.

- [ ] **Step 5: Lint the generated page**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix docs/reference/cube-data-catalog.md </dev/null`
Expected: no markdownlint issues (prettier fmt churn is applied at commit).

- [ ] **Step 6: Commit**

```bash
git add docs/reference/cube-data-catalog.md mkdocs.yml
git commit -m "docs(cube): generate field catalog and add to nav

Refs #4438"
```

---

## Task 7: `--verify-against-meta` backstop

**Files:**

- Modify: `scripts/generate_cube_reference.py` (replace the stub; add deps)
- Modify: `tests/scripts/test_generate_cube_reference.py` (add tests)

**Interfaces:**

- Consumes: `parse_cubes`, `parse_views`.
- Produces: `fetch_meta(base_url: str, secret: str, email: str) -> dict`;
  `meta_member_types(meta: dict) -> dict[str, dict[str, str]]`
  (`{view: {member: type}}`);
  `verify_against_meta(cubes_dir, views_dir, *, fetch=...) -> int`.
  `verify_against_meta` accepts an injectable `fetch` callable so tests run
  offline.

- [ ] **Step 1: Add runtime deps to the PEP-723 header**

Change the `dependencies` block at the top of the script to:

```python
# dependencies = [
#   "pyyaml>=6.0",
#   "pyjwt>=2.8",
#   "httpx>=0.27",
# ]
```

- [ ] **Step 2: Write the failing tests**

Append to the test file:

```python
def _fake_meta() -> dict:
    return {
        "cubes": [
            {
                "name": "sample_view",
                "measures": [{"name": "sample_view.count_rows", "type": "count"}],
                "dimensions": [
                    {"name": "sample_view.grade_level", "type": "number"},
                    {"name": "sample_view.no_desc_dim", "type": "string"},
                    {"name": "sample_view.sample_dim_region_name", "type": "string"},
                    {"name": "sample_view.base_key", "type": "string"},
                ],
            }
        ]
    }


def test_meta_member_types_strips_view_prefix() -> None:
    types = gen.meta_member_types(_fake_meta())
    assert types["sample_view"]["grade_level"] == "number"
    assert types["sample_view"]["count_rows"] == "count"


def test_verify_against_meta_passes_when_matching() -> None:
    rc = gen.verify_against_meta(
        FIXTURE_DIR / "cubes",
        FIXTURE_DIR / "views",
        fetch=lambda: _fake_meta(),
    )
    assert rc == 0


def test_verify_against_meta_fails_on_missing_member(capsys) -> None:
    meta = _fake_meta()
    meta["cubes"][0]["dimensions"] = [
        d for d in meta["cubes"][0]["dimensions"]
        if d["name"] != "sample_view.base_key"
    ]
    rc = gen.verify_against_meta(
        FIXTURE_DIR / "cubes", FIXTURE_DIR / "views", fetch=lambda: meta
    )
    assert rc == 1
    assert "base_key" in capsys.readouterr().err
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/scripts/test_generate_cube_reference.py -k meta -v`
Expected: FAIL — `meta_member_types` missing; stub returns 2.

- [ ] **Step 4: Implement the verifier**

Replace the temporary `verify_against_meta` stub with:

```python
import os


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

        def fetch() -> dict:
            return fetch_meta(base_url, secret, email)

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
```

Move the `import os` to the top-of-file import block (with the other stdlib
imports) rather than leaving it inline — it is shown inline here only to mark
where it is used.

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/scripts/test_generate_cube_reference.py -v` Expected:
PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_cube_reference.py tests/scripts/test_generate_cube_reference.py
git commit -m "feat(cube-docs): add --verify-against-meta backstop

Refs #4438"
```

---

## Task 8: Hand-written API guide + cross-links

**Files:**

- Create: `docs/guides/cube-api.md`
- Modify: `docs/guides/cube.md` (add a cross-link near the top)
- Modify: `mkdocs.yml` (nav entry under Guides)

**Interfaces:** none (docs task).

- [ ] **Step 1: Write the API guide**

Create `docs/guides/cube-api.md` with this content:

````markdown
# Cube API

How to query the Cube semantic layer — for external API developers, dashboard /
BI builders, and Claude MCP users. All three share one field surface: the
[Cube data catalog](../reference/cube-data-catalog.md) lists every view and the
fields it exposes.

## Start here

- **External / API developer** — read [Authentication](#authentication) then
  [Query format](#query-format); use the [REST example](#rest-api).
- **Dashboard / BI builder** — connect via the SQL API
  ([SQL example](#sql-api)); pick fields from the
  [catalog](../reference/cube-data-catalog.md). Access is filtered to your
  identity at connection time.
- **Claude MCP user** — no query syntax needed; see
  [Claude + Cube Connector](claude-cube-connector.md) and the
  [MCP example](#claude-mcp).

## Authentication

Cube resolves access from your identity — never a shared key. Requests carry an
HS256 JWT whose payload includes a top-level `email` claim; Cube resolves that
email against HR data into row- and column-level access (see
[how access is resolved](cube.md#how-access-is-resolved)).

- **Token:** an HS256 JWT signed with the deployment's API secret, payload
  `{"email": "you@apps.teamschools.org"}`.
- **Header:** `Authorization: <token>` — the raw token, **no `Bearer` prefix**.
- **Base URLs:** find the REST and SQL API URLs under **Cube Cloud → Settings →
  API Credentials** for the deployment. The MCP endpoint is configured for you
  by the connector.

No/invalid token is rejected; a valid token whose email resolves to no access
sees zero rows (default-deny).

## Query format

A REST query is a JSON object. The common keys:

| Key              | Purpose                                                                                       |
| ---------------- | --------------------------------------------------------------------------------------------- |
| `measures`       | Aggregations, dotted `<view>.<measure>` (e.g. `student_attendance_view.avg_daily_attendance`) |
| `dimensions`     | Group-by fields, dotted `<view>.<dimension>`                                                  |
| `filters`        | List of `{member, operator, values}` — see operators below                                    |
| `timeDimensions` | Date grouping/ranges: `{dimension, granularity, dateRange}`                                   |
| `order`          | `{member: "asc" \| "desc"}`                                                                   |
| `limit`          | Row cap                                                                                       |

Every member is dotted `<view>.<member>`; bare names do not resolve.

### Filter operators

Named, not SQL. Common ones: `equals`, `notEquals`, `contains`, `gt`, `gte`,
`lt`, `lte`, `set`, `notSet`, `inDateRange`, `beforeDate`, `afterDate`.
SQL-style `=` / `IN` / `LIKE` do not parse.

### Dates

For a single date use a `filters` entry with `equals`. For a range or when you
need a `granularity` (day/week/month/…), use `timeDimensions` with `dateRange`.

### Academic year

`academic_year` is the **start** year: `academic_year` 2025 means the 2025-26
school year (`academic_year_label` `"2025-2026"`, "SY26"). Prefer
`academic_year_label` when filtering — it is unambiguous.

## Error handling

- **Field outside your tier → the whole query is blocked**, not silently
  trimmed. Cube returns an error naming the hidden member; it does not drop the
  column and return the rest. Build BI workbooks from fields your least-
  privileged audience can see (SQL-API tools like Superset filter the field list
  per user at connect time and avoid this).
- **No matching reader group → zero rows** (default-deny). `/meta` also returns
  no cubes in this case — it is access-filtered, not empty.

## Examples

Each example returns network-wide average daily attendance for one academic year
— the same figure by three paths.

### REST API

```bash
tok=$(node -e "const j=require('jsonwebtoken');console.log(j.sign({email:'you@apps.teamschools.org'},process.env.CUBEJS_API_SECRET,{algorithm:'HS256'}))")
curl -s -H "Authorization: $tok" -H 'Content-Type: application/json' \
  -X POST --data '{"query":{
    "measures":["student_attendance_view.avg_daily_attendance"],
    "timeDimensions":[{"dimension":"student_attendance_view.attendance_date",
                       "dateRange":["2025-07-01","2026-06-30"]}]
  }}' \
  <REST_BASE_URL>/load
```

Replace `<REST_BASE_URL>` with the deployment's REST API base (from API
Credentials, ending in `/cubejs-api/v1`).

### SQL API

```python
import psycopg2  # connect as your email; identity resolves from the SQL user

conn = psycopg2.connect(host="<SQL_HOST>", port=<SQL_PORT>,
                        user="you@apps.teamschools.org",
                        password="<SQL_PASSWORD>", dbname="cube")
cur = conn.cursor()
cur.execute(
    "SELECT MEASURE(avg_daily_attendance) FROM student_attendance_view"
)
print(cur.fetchall())
```

### Claude MCP

Ask in plain English — no field names or SQL:

```text
What was network-wide average daily attendance for the 2025-26 school year?
```

Claude picks the Cube tool, runs the query under your identity, and returns the
answer. See [Claude + Cube Connector](claude-cube-connector.md).
````

- [ ] **Step 2: Cross-link from the Cube hub**

In `docs/guides/cube.md`, immediately after the first paragraph (the one ending
"…all downstream consumers."), add:

```markdown
!!! tip "Looking to query Cube?"

    See the [Cube API guide](cube-api.md) for auth and query format, and the
    [Cube data catalog](../reference/cube-data-catalog.md) for every view and
    field.
```

- [ ] **Step 3: Add the nav entry**

In `mkdocs.yml` `nav:`, under `Guides:`, add directly after the `Cube:` line:

```yaml
- Cube: guides/cube.md
- Cube API: guides/cube-api.md
- Claude + Cube Connector: guides/claude-cube-connector.md
```

- [ ] **Step 4: Lint and build**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix docs/guides/cube-api.md docs/guides/cube.md </dev/null`
Expected: no markdownlint issues.

Run: `uv run --group docs mkdocs build 2>&1 | tail -20` Expected: build
succeeds; both new pages present.

- [ ] **Step 5: Commit**

```bash
git add docs/guides/cube-api.md docs/guides/cube.md mkdocs.yml
git commit -m "docs(cube): add API guide and cross-links

Refs #4438"
```

---

## Task 9: CI freshness workflow

**Files:**

- Create: `.github/workflows/cube-docs-check.yaml`

**Interfaces:** none.

> **Handoff note:** the Codespace `ghu_*` token lacks the `workflow` scope, so
> Claude cannot push a new/changed workflow file. Commit it locally; the **user
> pushes** this commit (or the whole branch) from their terminal.

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/cube-docs-check.yaml`:

```yaml
name: Cube Docs Freshness

on:
  pull_request:
    paths:
      - src/cube/model/**
      - scripts/generate_cube_reference.py
      - docs/reference/cube-data-catalog.md

permissions:
  contents: read

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: astral-sh/setup-uv@v7
      - name: Check catalog is up to date
        run: uv run scripts/generate_cube_reference.py --check
```

- [ ] **Step 2: Verify the check locally (both directions)**

Confirm a clean tree passes:

Run: `uv run scripts/generate_cube_reference.py --check && echo PASS` Expected:
`PASS`.

Confirm a staleness is caught (edit a fixture-independent real description
temporarily, do NOT commit):

Run:

```bash
uv run scripts/generate_cube_reference.py --output /tmp/cat.md
# simulate drift: check the committed file against a doctored page
cp docs/reference/cube-data-catalog.md /tmp/orig.md
printf '\n<!-- drift -->\n' >> docs/reference/cube-data-catalog.md
uv run scripts/generate_cube_reference.py --check; echo "exit=$?"
git checkout -- docs/reference/cube-data-catalog.md
```

Expected: `exit=1` (stale detected), then the file is restored.

- [ ] **Step 3: Commit (user pushes)**

```bash
git add .github/workflows/cube-docs-check.yaml
git commit -m "ci(cube-docs): fail PRs when the catalog is stale

Refs #4438"
```

Then tell the user: "The workflow file is committed locally — please push the
branch from your terminal (the Codespace token can't push workflow changes)."

---

## Task 10: Document the generator

**Files:**

- Modify: `docs/CLAUDE.md` (Generated Content section)
- Modify: `scripts/CLAUDE.md` (Script Catalog + Prerequisites)

**Interfaces:** none.

- [ ] **Step 1: Update `docs/CLAUDE.md`**

In `docs/CLAUDE.md`, under `## Generated Content`, after the
`reference/automations.md` paragraph, add:

```markdown
**`reference/cube-data-catalog.md`** is auto-generated by
`uv run scripts/generate_cube_reference.py` from the Cube model YAML
(`src/cube/model/`). Never edit it directly. Regenerate after adding or changing
a cube or view; the `Cube Docs Freshness` CI workflow fails PRs whose committed
catalog is stale. Only members a view exposes are documented — private cubes
never surface.
```

- [ ] **Step 2: Update `scripts/CLAUDE.md`**

In `scripts/CLAUDE.md`, add a row to the Script Catalog table (after the
`generate_marts_reference.py` row):

```markdown
| `generate_cube_reference.py` | Regenerate
`docs/reference/cube-data-catalog.md` from Cube model YAML (parses
`src/cube/model/`; no network). `--check` for CI, `--verify-against-meta` for
the live cross-check |
```

And under `## Prerequisites`, add:

```markdown
- `generate_cube_reference.py` — no prerequisites for the default/`--check`
  paths (parses YAML only): `uv run scripts/generate_cube_reference.py`. Like
  `automations.md`, commit the prettier-padded output — table-padding churn
  between run and commit is expected. `--verify-against-meta` additionally needs
  `CUBE_META_URL`, `CUBE_API_SECRET`, and `CUBE_META_EMAIL` (a broad-access
  identity) and reaches the live `/meta` endpoint.
```

- [ ] **Step 3: Lint**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix docs/CLAUDE.md scripts/CLAUDE.md </dev/null`
Expected: no issues.

- [ ] **Step 4: Commit**

```bash
git add docs/CLAUDE.md scripts/CLAUDE.md
git commit -m "docs(cube): document the catalog generator

Refs #4438"
```

---

## Final verification

- [ ] **Full test suite for the generator**

Run: `uv run pytest tests/scripts/test_generate_cube_reference.py -v` Expected:
all tests PASS.

- [ ] **Catalog is fresh**

Run: `uv run scripts/generate_cube_reference.py --check && echo CLEAN` Expected:
`CLEAN`.

- [ ] **Site builds**

Run: `uv run --group docs mkdocs build 2>&1 | tail -5` Expected: build succeeds
with both new pages.

- [ ] **Open the PR** (use `.github/pull_request_template.md` as the body; the
      branch already links issue #4438; remind the user to push if the workflow
      file is unpushed).
