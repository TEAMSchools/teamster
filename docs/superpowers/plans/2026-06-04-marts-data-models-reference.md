# Marts Data-Model Reference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate an MkDocs reference page documenting every `kipptaf` fact
table with a Mermaid ER snowflake diagram (full FK chain) and a foreign-key
table.

**Architecture:** A pure-Python generator parses FK `constraints` from the marts
properties YAML, builds a directed FK graph, BFS-traverses the full snowflake
chain per fact, and emits one markdown page. MkDocs Material renders the
`mermaid` fences client-side once a superfences custom fence is added.

**Tech Stack:** Python 3.13 (PEP 723 inline deps), PyYAML, pytest, MkDocs
Material.

**Worktree:** All work happens in `.worktrees/cbini-docs-marts-reference` on
branch `cbini/docs/claude-marts-data-models-reference`. Commands below use the
worktree path explicitly so they work when run from the main repo. Tracking
issue: [#4120](https://github.com/TEAMSchools/teamster/issues/4120).

---

## File Structure

- Create: `scripts/generate_marts_reference.py` — the generator (parse → graph →
  render → write).
- Create: `tests/scripts/test_generate_marts_reference.py` — unit tests for the
  pure functions.
- Create: `tests/scripts/fixtures/sample_fct_reference.yml` — minimal fixture
  for `parse_fk_edges`.
- Create: `docs/reference/marts-data-models.md` — the generated page (output,
  committed).
- Modify: `mkdocs.yml` — add the `mermaid` superfences custom fence and the nav
  entry.
- Modify: `scripts/CLAUDE.md` — one-line regeneration note.

The generator is one focused module: small pure functions (`parse_fk_edges`,
`collect_edges`, `collect_fact_names`, `build_adjacency`, `snowflake_subgraph`,
`render_*`) plus a thin `main()`. This mirrors `scripts/audit_marts_yaml.py`
(PEP 723 header, `pathlib`, dataclasses) and its test in
`tests/scripts/test_audit_marts_yaml.py` (loads the script via
`importlib.util`).

---

## Task 1: Parse FK edges from a properties YAML

**Files:**

- Create: `scripts/generate_marts_reference.py`
- Create: `tests/scripts/fixtures/sample_fct_reference.yml`
- Test: `tests/scripts/test_generate_marts_reference.py`

- [ ] **Step 1: Create the test fixture**

Create `tests/scripts/fixtures/sample_fct_reference.yml`:

```yaml
models:
  - name: fct_sample
    columns:
      - name: sample_key
        constraints:
          - type: primary_key
      - name: student_enrollment_key
        constraints:
          - type: foreign_key
            to: ref('dim_student_enrollments')
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_student_enrollments')
                field: student_enrollment_key
      - name: created_date_key
        constraints:
          - type: foreign_key
            to: ref('dim_dates')
      - name: solved_date_key
        constraints:
          - type: foreign_key
            to: ref('dim_dates')
```

- [ ] **Step 2: Write the failing test**

Create `tests/scripts/test_generate_marts_reference.py`:

```python
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts/generate_marts_reference.py"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "generate_marts_reference", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_marts_reference"] = module
    spec.loader.exec_module(module)
    return module


gen = _load_module()


def test_parse_fk_edges_reads_foreign_key_constraints() -> None:
    edges = gen.parse_fk_edges(FIXTURE_DIR / "sample_fct_reference.yml")

    # one edge per foreign_key constraint; primary_key ignored; relationships
    # test is NOT double-counted.
    assert edges == [
        gen.FkEdge("fct_sample", "student_enrollment_key", "dim_student_enrollments"),
        gen.FkEdge("fct_sample", "created_date_key", "dim_dates"),
        gen.FkEdge("fct_sample", "solved_date_key", "dim_dates"),
    ]
```

- [ ] **Step 3: Run the test to verify it fails**

Run:

```bash
VIRTUAL_ENV= uv --directory .worktrees/cbini-docs-marts-reference run \
  pytest tests/scripts/test_generate_marts_reference.py -v
```

Expected: FAIL — `scripts/generate_marts_reference.py` does not exist
(collection error).

- [ ] **Step 4: Write the minimal implementation**

Create `scripts/generate_marts_reference.py`:

```python
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "pyyaml>=6.0",
# ]
# ///

"""Generate the marts data-model reference page.

Parses foreign-key constraints from the kipptaf marts properties YAML, builds a
directed FK graph, traverses the full snowflake chain per fact table, and emits
a single markdown page with a Mermaid ER diagram and an FK table per fact.

No dbt build or warehouse access required.

Usage:
    uv run scripts/generate_marts_reference.py

Design reference:
    docs/superpowers/specs/2026-06-04-marts-data-models-reference-design.md
"""

from __future__ import annotations

import argparse
import dataclasses
import re
from collections import defaultdict, deque
from collections.abc import Iterable, Mapping
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MARTS_DIR = REPO_ROOT / "src/dbt/kipptaf/models/marts"
DEFAULT_OUTPUT = REPO_ROOT / "docs/reference/marts-data-models.md"

_REF_RE = re.compile(r"ref\(\s*['\"]([a-z0-9_]+)['\"]\s*\)")


@dataclasses.dataclass(frozen=True)
class FkEdge:
    """A foreign-key edge from a model's column to a target model."""

    source: str
    fk_column: str
    target: str


def _extract_target(to_value: str) -> str | None:
    match = _REF_RE.search(to_value)
    return match.group(1) if match else None


def parse_fk_edges(yaml_path: Path) -> list[FkEdge]:
    """Return one FkEdge per column-level foreign_key constraint in the file."""
    doc = yaml.safe_load(yaml_path.read_text()) or {}
    edges: list[FkEdge] = []
    for model in doc.get("models", []):
        source = model["name"]
        for column in model.get("columns", []):
            for constraint in column.get("constraints", []):
                if constraint.get("type") != "foreign_key":
                    continue
                target = _extract_target(str(constraint.get("to", "")))
                if target is not None:
                    edges.append(FkEdge(source, column["name"], target))
    return edges
```

- [ ] **Step 5: Run the test to verify it passes**

Run:

```bash
VIRTUAL_ENV= uv --directory .worktrees/cbini-docs-marts-reference run \
  pytest tests/scripts/test_generate_marts_reference.py -v
```

Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git -C .worktrees/cbini-docs-marts-reference add \
  scripts/generate_marts_reference.py \
  tests/scripts/fixtures/sample_fct_reference.yml \
  tests/scripts/test_generate_marts_reference.py
git -C .worktrees/cbini-docs-marts-reference commit -m "feat: add marts reference FK-edge parser

Refs #4120"
```

---

## Task 2: Build the FK graph and traverse the snowflake chain

**Files:**

- Modify: `scripts/generate_marts_reference.py` (add functions)
- Test: `tests/scripts/test_generate_marts_reference.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/scripts/test_generate_marts_reference.py`:

```python
def _sample_edges() -> list:
    return [
        gen.FkEdge("fct_x", "enrollment_key", "dim_enrollments"),
        gen.FkEdge("fct_x", "created_date_key", "dim_dates"),
        gen.FkEdge("fct_x", "solved_date_key", "dim_dates"),
        gen.FkEdge("dim_enrollments", "student_key", "dim_students"),
        gen.FkEdge("dim_enrollments", "location_key", "dim_locations"),
        gen.FkEdge("dim_locations", "region_key", "dim_regions"),
    ]


def test_build_adjacency_groups_edges_by_source() -> None:
    adjacency = gen.build_adjacency(_sample_edges())
    assert {e.target for e in adjacency["fct_x"]} == {"dim_enrollments", "dim_dates"}
    assert len(adjacency["fct_x"]) == 3  # two role-qualified date edges kept


def test_snowflake_subgraph_walks_full_chain() -> None:
    adjacency = gen.build_adjacency(_sample_edges())
    sub = gen.snowflake_subgraph(adjacency, "fct_x")

    # every reachable edge is collected (full snowflake chain), including both
    # role-qualified edges to dim_dates and the dim->dim chain to dim_regions.
    assert len(sub) == 6
    assert gen.FkEdge("dim_locations", "region_key", "dim_regions") in sub
    targets = {e.target for e in sub}
    assert {"dim_regions", "dim_students", "dim_dates"} <= targets


def test_collect_fact_names_sorted_from_facts_dir() -> None:
    names = gen.collect_fact_names(gen.MARTS_DIR)
    assert names == sorted(names)
    assert all(n.startswith("fct_") for n in names)
    assert "fct_student_attendance_daily" in names
    assert len(names) >= 20
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
VIRTUAL_ENV= uv --directory .worktrees/cbini-docs-marts-reference run \
  pytest tests/scripts/test_generate_marts_reference.py -v
```

Expected: FAIL — `build_adjacency`, `snowflake_subgraph`, `collect_fact_names`
not defined.

- [ ] **Step 3: Add the implementation**

Insert these functions into `scripts/generate_marts_reference.py`, after
`parse_fk_edges`:

```python
def collect_edges(marts_dir: Path) -> list[FkEdge]:
    """Parse FK edges from every facts/dimensions/bridges properties file."""
    edges: list[FkEdge] = []
    for subdir in ("facts", "dimensions", "bridges"):
        for path in sorted((marts_dir / subdir / "properties").glob("*.yml")):
            edges.extend(parse_fk_edges(path))
    return edges


def collect_fact_names(marts_dir: Path) -> list[str]:
    """Return the sorted list of fct_* model names from facts/properties."""
    names: list[str] = []
    for path in sorted((marts_dir / "facts" / "properties").glob("*.yml")):
        doc = yaml.safe_load(path.read_text()) or {}
        names.extend(
            model["name"]
            for model in doc.get("models", [])
            if model["name"].startswith("fct_")
        )
    return sorted(names)


def build_adjacency(edges: Iterable[FkEdge]) -> dict[str, list[FkEdge]]:
    """Group edges by source model into an adjacency map."""
    adjacency: dict[str, list[FkEdge]] = defaultdict(list)
    for edge in edges:
        adjacency[edge.source].append(edge)
    return adjacency


def snowflake_subgraph(
    adjacency: Mapping[str, list[FkEdge]], root: str
) -> list[FkEdge]:
    """BFS from root, collecting every reachable FK edge (full snowflake chain).

    Each target node is enqueued once; role-qualified parallel edges to the same
    target are all kept. Assumes a DAG (no diamonds, per the marts design).
    """
    visited: set[str] = {root}
    queue: deque[str] = deque([root])
    collected: list[FkEdge] = []
    seen: set[tuple[str, str, str]] = set()
    while queue:
        node = queue.popleft()
        for edge in adjacency.get(node, []):
            key = (edge.source, edge.fk_column, edge.target)
            if key not in seen:
                seen.add(key)
                collected.append(edge)
            if edge.target not in visited:
                visited.add(edge.target)
                queue.append(edge.target)
    return collected
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
VIRTUAL_ENV= uv --directory .worktrees/cbini-docs-marts-reference run \
  pytest tests/scripts/test_generate_marts_reference.py -v
```

Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git -C .worktrees/cbini-docs-marts-reference add \
  scripts/generate_marts_reference.py \
  tests/scripts/test_generate_marts_reference.py
git -C .worktrees/cbini-docs-marts-reference commit -m "feat: add FK graph build and snowflake traversal

Refs #4120"
```

---

## Task 3: Render the Mermaid diagram, FK table, and page

**Files:**

- Modify: `scripts/generate_marts_reference.py` (add render functions)
- Test: `tests/scripts/test_generate_marts_reference.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/scripts/test_generate_marts_reference.py`:

````python
def test_render_erdiagram_emits_labeled_fk_edges() -> None:
    adjacency = gen.build_adjacency(_sample_edges())
    sub = gen.snowflake_subgraph(adjacency, "fct_x")
    block = gen.render_erdiagram(sub, "fct_x")

    assert block.startswith("```mermaid\nerDiagram\n")
    assert block.rstrip().endswith("```")
    assert 'fct_x }o--|| dim_dates : "created_date_key"' in block
    assert 'fct_x }o--|| dim_dates : "solved_date_key"' in block
    assert 'dim_locations }o--|| dim_regions : "region_key"' in block


def test_render_erdiagram_handles_fact_with_no_fks() -> None:
    block = gen.render_erdiagram([], "fct_lonely")
    assert "erDiagram" in block
    assert "fct_lonely {" in block


def test_render_fk_table_lists_direct_fks_sorted() -> None:
    adjacency = gen.build_adjacency(_sample_edges())
    table = gen.render_fk_table(adjacency, "fct_x")

    assert "| FK column | References |" in table
    lines = [ln for ln in table.splitlines() if ln.startswith("| `")]
    # direct FKs only, sorted by column name
    assert lines == [
        "| `created_date_key` | `dim_dates` |",
        "| `enrollment_key` | `dim_enrollments` |",
        "| `solved_date_key` | `dim_dates` |",
    ]


def test_render_page_has_one_h2_per_fact_and_banner() -> None:
    adjacency = gen.build_adjacency(_sample_edges())
    page = gen.render_page(adjacency, ["fct_x"])

    assert page.startswith("# Marts data models\n")
    assert gen.BANNER in page
    assert page.count("\n## ") == 1
    assert "## fct_x" in page
````

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
VIRTUAL_ENV= uv --directory .worktrees/cbini-docs-marts-reference run \
  pytest tests/scripts/test_generate_marts_reference.py -v
```

Expected: FAIL — `render_erdiagram`, `render_fk_table`, `render_page`, `BANNER`
not defined.

- [ ] **Step 3: Add the implementation**

Insert into `scripts/generate_marts_reference.py`, after `snowflake_subgraph`:

````python
BANNER = (
    "<!-- generated by scripts/generate_marts_reference.py; "
    "do not edit by hand -->"
)

INTRO = """\
The `kipptaf` marts are dimensional models (fact and dimension tables) consumed
by Cube and Tableau. They follow a **strict-chain snowflake** design: each fact
table holds foreign keys to its _direct_ parents only, and deeper context is
reached by chaining one dimension to its parent dimension
(`fct_student_attendance_daily` → `dim_student_enrollments` → `dim_students`).

Each section below shows one fact table and the full snowflake chain reachable
from it, followed by the fact's own foreign keys.

> **Reading the diagrams.** Boxes are tables (`fct_*` facts, `dim_*`
> dimensions). An edge `child }o--|| parent : "fk_column"` reads "many rows of
> _child_ reference one row of _parent_ via _fk_column_." A fact with several
> edges to the same dimension (e.g. `created_date_key` and `solved_date_key`
> both to `dim_dates`) is showing role-qualified foreign keys.
"""


def render_erdiagram(edges: list[FkEdge], root: str) -> str:
    lines = ["```mermaid", "erDiagram"]
    if edges:
        for edge in edges:
            lines.append(
                f'  {edge.source} }}o--|| {edge.target} : "{edge.fk_column}"'
            )
    else:
        lines.append(f"  {root} {{")
        lines.append("  }")
    lines.append("```")
    return "\n".join(lines)


def render_fk_table(adjacency: Mapping[str, list[FkEdge]], root: str) -> str:
    direct = sorted(adjacency.get(root, []), key=lambda e: e.fk_column)
    lines = ["| FK column | References |", "| --- | --- |"]
    lines.extend(f"| `{edge.fk_column}` | `{edge.target}` |" for edge in direct)
    return "\n".join(lines)


def render_fact_section(adjacency: Mapping[str, list[FkEdge]], fact: str) -> str:
    sub = snowflake_subgraph(adjacency, fact)
    return "\n".join(
        [
            f"## {fact}",
            "",
            render_erdiagram(sub, fact),
            "",
            "**Foreign keys**",
            "",
            render_fk_table(adjacency, fact),
        ]
    )


def render_page(adjacency: Mapping[str, list[FkEdge]], facts: list[str]) -> str:
    sections = [render_fact_section(adjacency, fact) for fact in facts]
    body = "\n\n".join(["# Marts data models", BANNER, INTRO.rstrip(), *sections])
    return body + "\n"
````

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
VIRTUAL_ENV= uv --directory .worktrees/cbini-docs-marts-reference run \
  pytest tests/scripts/test_generate_marts_reference.py -v
```

Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git -C .worktrees/cbini-docs-marts-reference add \
  scripts/generate_marts_reference.py \
  tests/scripts/test_generate_marts_reference.py
git -C .worktrees/cbini-docs-marts-reference commit -m "feat: add Mermaid ER diagram and page rendering

Refs #4120"
```

---

## Task 4: Wire up main(), generate the real page, and commit it

**Files:**

- Modify: `scripts/generate_marts_reference.py` (add `main()`)
- Create: `docs/reference/marts-data-models.md` (generated output)

- [ ] **Step 1: Add `main()` to the script**

Append to `scripts/generate_marts_reference.py`:

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marts-dir", type=Path, default=MARTS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    edges = collect_edges(args.marts_dir)
    adjacency = build_adjacency(edges)
    facts = collect_fact_names(args.marts_dir)
    page = render_page(adjacency, facts)
    args.output.write_text(page)
    print(f"wrote {len(facts)} fact sections to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the generator**

Run:

```bash
VIRTUAL_ENV= uv --directory .worktrees/cbini-docs-marts-reference run \
  python scripts/generate_marts_reference.py
```

Expected: prints
`wrote 24 fact sections to .../docs/reference/marts-data-models.md`.

- [ ] **Step 3: Spot-check the output against source YAML**

Run:

```bash
grep -c '^## fct_' .worktrees/cbini-docs-marts-reference/docs/reference/marts-data-models.md
grep -A2 '^## fct_support_tickets' .worktrees/cbini-docs-marts-reference/docs/reference/marts-data-models.md | head
```

Expected: count is `24`; the `fct_support_tickets` section shows an `erDiagram`
with role-qualified `submitter_staff_key` / `assignee_staff_key` /
`original_assignee_staff_key` edges to `dim_staff`.

Then confirm every `foreign_key` constraint on one fact appears as an FK-table
row:

```bash
grep -c "type: foreign_key" \
  .worktrees/cbini-docs-marts-reference/src/dbt/kipptaf/models/marts/facts/properties/fct_support_tickets.yml
grep -A40 '^## fct_support_tickets' \
  .worktrees/cbini-docs-marts-reference/docs/reference/marts-data-models.md \
  | grep -c '^| `'
```

Expected: the FK-table row count equals the number of `foreign_key` constraints
on that fact (6).

- [ ] **Step 4: Run the full test suite for the script**

Run:

```bash
VIRTUAL_ENV= uv --directory .worktrees/cbini-docs-marts-reference run \
  pytest tests/scripts/test_generate_marts_reference.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit (pre-commit `trunk fmt` will format the markdown)**

```bash
git -C .worktrees/cbini-docs-marts-reference add \
  scripts/generate_marts_reference.py \
  docs/reference/marts-data-models.md
git -C .worktrees/cbini-docs-marts-reference commit -m "docs: generate marts data-model reference page

Refs #4120"
```

Note: `trunk-fmt-pre-commit` (prettier) reformats `marts-data-models.md` at
commit — the committed file is the formatted form, and re-running the
generator + committing is stable thereafter (prettier leaves the `mermaid` fence
contents untouched).

---

## Task 5: Enable Mermaid in MkDocs and add the nav entry

**Files:**

- Modify: `mkdocs.yml`

- [ ] **Step 1: Add the mermaid custom fence**

In `mkdocs.yml`, replace the bare superfences line under `markdown_extensions:`:

```yaml
- pymdownx.superfences
```

with the mapping form:

```yaml
- pymdownx.superfences:
    custom_fences:
      - name: mermaid
        class: mermaid
        format: !!python/name:pymdownx.superfences.fence_code_format
```

- [ ] **Step 2: Add the nav entry**

In `mkdocs.yml`, under the `Reference:` nav section, add a line after
`dbt Conventions`:

```yaml
- Marts Data Models: reference/marts-data-models.md
```

- [ ] **Step 3: Build the site**

Run:

```bash
VIRTUAL_ENV= uv --directory .worktrees/cbini-docs-marts-reference run \
  mkdocs build --site-dir /tmp/marts-docs-build 2>&1 | tee /tmp/marts-build.log | tail -5
```

Expected: ends with `Documentation built in N seconds` and exits 0. Do **not**
use `--strict`: this repo has ~58 pre-existing warnings (broken links and
not-in-nav pages under `docs/superpowers/**`) that abort strict mode and are
unrelated to this change.

Then confirm the new page introduced no warnings of its own (it is in nav and
has no markdown links):

```bash
grep -i 'marts-data-models' /tmp/marts-build.log \
  && echo "FAIL: new page produced a warning" \
  || echo "OK: no warnings reference the new page"
```

Expected: `OK: no warnings reference the new page`.

- [ ] **Step 4: Confirm Mermaid blocks render as `class="mermaid"`**

Run:

```bash
grep -c 'class="mermaid"' /tmp/marts-docs-build/reference/marts-data-models/index.html
```

Expected: a count of `24` (one rendered block per fact). A count of `0` means
the custom fence is mis-configured.

- [ ] **Step 5: Commit**

```bash
git -C .worktrees/cbini-docs-marts-reference add mkdocs.yml
git -C .worktrees/cbini-docs-marts-reference commit -m "docs: enable mermaid fence and add marts reference to nav

Refs #4120"
```

---

## Task 6: Document regeneration

**Files:**

- Modify: `scripts/CLAUDE.md`

- [ ] **Step 1: Add a regeneration note**

Read `scripts/CLAUDE.md` first to match its existing structure, then add an
entry documenting:

```text
- `generate_marts_reference.py` — regenerates
  `docs/reference/marts-data-models.md` from the marts FK constraints. Run after
  adding/removing a fact or changing FK constraints:
  `uv run scripts/generate_marts_reference.py`.
```

(Place it consistent with how other scripts are listed in that file; if there is
no per-script list, add a short "Generated docs" subsection.)

- [ ] **Step 2: Verify the doc edit is clean**

Run:

```bash
.trunk/tools/trunk check --force \
  /workspaces/teamster/.worktrees/cbini-docs-marts-reference/scripts/CLAUDE.md
```

Run from inside the worktree directory. Expected: no issues.

- [ ] **Step 3: Commit**

```bash
git -C .worktrees/cbini-docs-marts-reference add scripts/CLAUDE.md
git -C .worktrees/cbini-docs-marts-reference commit -m "docs: note marts reference regeneration in scripts/CLAUDE.md

Refs #4120"
```

---

## Final verification

- [ ] All script tests pass:

```bash
VIRTUAL_ENV= uv --directory .worktrees/cbini-docs-marts-reference run \
  pytest tests/scripts/test_generate_marts_reference.py -v
```

- [ ] `mkdocs build` (non-strict) exits 0 and the new page produces no warnings
      (Task 5, Step 3); its HTML has 24 `class="mermaid"` blocks (Step 4).
- [ ] `git -C .worktrees/cbini-docs-marts-reference status` shows a clean tree
      (no stray `site/` or `/tmp` artifacts tracked).
- [ ] Regenerating is idempotent: re-run the generator; `git status` shows no
      diff to `docs/reference/marts-data-models.md`.

---

## Notes for the executor

- This repo requires `uv run` — never bare `python`/`pytest`.
- Run git and dbt/python via the worktree path (`git -C .worktrees/...`,
  `uv --directory .worktrees/...`) so changes land on the feature branch, not
  `main`.
- Do not run `trunk fmt`/`trunk check` manually except where Task 6 calls for
  `trunk check --force` from inside the worktree — the pre-commit hook formats
  on commit.
- PR comes after the plan completes; use `.github/pull_request_template.md` and
  `Closes #4120`.
