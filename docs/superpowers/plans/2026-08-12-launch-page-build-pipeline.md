# Launch page build pipeline — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the launch page prototype into a tested, gated build that renders
the staff tool catalog into the docs site.

**Architecture:** A four-function module (`load` / `select` / `validate` /
`render`) called from an MkDocs `on_files` hook. `render()` returns an HTML
string; nothing in the module writes to disk. Two-tier validation lets
in-progress entries through and stops malformed published ones. A minimum
verified count suppresses the page entirely rather than shipping a broken one.

**Tech Stack:** Python 3.13, PyYAML, pytest, MkDocs 1.6.1 (`File.generated`),
GitHub Actions, `uv`.

**Spec:** `docs/superpowers/specs/2026-08-11-launch-page-build-gate-design.md`

## Global Constraints

- Everything lives at `docs/launch/`, not `src/launch/`. The spec says
  `src/launch/`; that decision was reversed after the spec merged. Paths below
  are authoritative.
- Always `uv run`. Never bare `python` / `pytest`.
- `render()` returns `str | None`. It must never write a file.
- Validation errors accumulate. One run reports every problem.
- YAML: quote a scalar only when YAML requires it (a value containing `: `).
  Redundant quotes fail yamllint at pre-push, not at commit.
- Markdown: every fenced block gets a language (MD040); use `1.` for every item
  in an ordered list broken by fences (MD029).
- Run `.trunk/tools/trunk check --force <files>` from inside the worktree before
  pushing. The commit hook only runs `fmt`.
- Worktree: `/workspaces/teamster/.worktrees/launch-build-pipeline`. Use
  `git -C <worktree>` for every git call.

## Two spec assumptions that the merge of #4767 invalidated

Read this before Task 1; it changes what gets built.

**The catalog is now 44 entries with 39 verified**, not 46 with zero. The spec
was written when nothing was verified.

**Consequence: the page will publish on the first deploy.** 39 is above the
threshold of 25. The spec deferred the per-entry `group` field and specified a
flat alphabetical list, justified by "the threshold means no page is generated
at all until well after the follow-up lands, so the flat layout is never what
staff see." That is now false — a flat list of 39 tools would go straight to
staff.

The reason for the deferral was that 37 entries were in flight on #4767. That PR
merged. **So `group` is folded into this plan (Task 5) rather than deferred**,
and `render()` is written grouped the first time in Task 6.

---

### Task 1: Move the catalog to `docs/launch/` and fix the config that follows

**Files:**

- Move: `src/launch/{links.yml,README.md,RUNBOOK.md,PROJECT.md}` →
  `docs/launch/`
- Delete: `src/launch/views.yml`
- Modify: `mkdocs.yml`, `.github/CODEOWNERS`, `docs/CLAUDE.md`, `pyproject.toml`

**Interfaces:**

- Consumes: nothing.
- Produces: `docs/launch/links.yml` — the catalog every later task reads.

`views.yml` is deleted rather than moved: the launch page design retires it, its
per-view intro copy moves into the template, and nothing reads it.

No `watch:` key is needed. The spec adds `watch: [src/launch]` because
`src/launch` sat outside `docs_dir`. At `docs/launch/` it is inside, and
`mkdocs/commands/serve.py:89` watches `config.docs_dir` wholesale without
consulting `exclude_docs` — so the catalog is watched and excluded files still
trigger rebuilds.

No `mkdocs-gh-deploy.yaml` change is needed either. Its `paths` already includes
`docs/**`.

- [ ] **Step 1: Move the files**

```bash
cd /workspaces/teamster/.worktrees/launch-build-pipeline
mkdir -p docs/launch
git mv src/launch/links.yml docs/launch/links.yml
git mv src/launch/README.md docs/launch/README.md
git mv src/launch/RUNBOOK.md docs/launch/RUNBOOK.md
git mv src/launch/PROJECT.md docs/launch/PROJECT.md
git rm src/launch/views.yml
```

- [ ] **Step 2: Stop MkDocs publishing the source files**

Everything in `docs_dir` is copied to the site verbatim — `docs/hooks.py` is
live at `/teamster/hooks.py` today, which proves it. Add to `mkdocs.yml`, after
the `hooks:` block:

```yaml
exclude_docs: |
  hooks.py
  launch/*.yml
  launch/*.py
  launch/template.html
  launch/RUNBOOK.md
```

`README.md` and `PROJECT.md` are deliberately left publishable — they are useful
as public pages. `RUNBOOK.md` is excluded because it carries intern task
sequencing.

- [ ] **Step 3: Preserve ownership**

`/docs/` belongs to `data-team`, so the move would silently reverse #4816. Add
to `.github/CODEOWNERS`, immediately after the `/docs/` line:

```text
/docs/launch/ @TEAMSchools/admins @TEAMSchools/analytics-engineers
```

- [ ] **Step 4: Widen the stated scope of `docs/`**

`docs/CLAUDE.md` opens by scoping the directory to "engineering documentation".
A tool catalog and a build script are not that. Replace the first paragraph:

```markdown
MkDocs site for **engineering** documentation — architecture, operational
guides, and infrastructure patterns — plus `launch/`, the staff tool catalog and
the build that renders it into a page. Analyst documentation lives in dbt YAML
(properties files + exposures), not here.
```

- [ ] **Step 5: Declare PyYAML**

It currently resolves only transitively through mkdocs. In `pyproject.toml`:

```toml
docs = ["mkdocs-material>=9.7", "pyyaml>=6.0"]
```

- [ ] **Step 6: Sweep the path references**

```bash
cd /workspaces/teamster/.worktrees/launch-build-pipeline
grep -rl 'src/launch' --include='*.md' --include='*.yml' --include='*.yaml' \
  --include='*.py' . \
  | grep -v '^./.git' \
  | grep -v 'docs/superpowers/specs/' \
  | xargs sed -i 's|src/launch|docs/launch|g'
git -C . diff --stat
```

The specs under `docs/superpowers/specs/` are excluded deliberately. A blind
substitution there produces false statements — the build-gate spec argues that
"`src/launch/` is not under `docs_dir`", which is the reason it adds a `watch:`
key, and rewriting the path inverts the claim. Instead add one line under that
spec's title:

```markdown
> **Superseded on location:** this design says `src/launch/`. The catalog moved
> to `docs/launch/` after the spec merged; see the implementation plan dated
> 2026-08-12. Everything else here still holds.
```

Then re-read `docs/launch/PROJECT.md` and correct its stale counts by hand: it
says 46 entries and zero verified. It is 44 and 39.

- [ ] **Step 7: Verify the site still builds**

Run: `uv run --group docs mkdocs build --site-dir /tmp/launch-check` Expected:
exits 0. Then confirm the source files did not publish:

```bash
ls /tmp/launch-check/launch/ 2>&1
```

Expected: `No such file or directory` — nothing from `docs/launch/` is copied.

- [ ] **Step 8: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/launch-build-pipeline
~/.cache/trunk/launcher/trunk check --force --no-fix mkdocs.yml \
  .github/CODEOWNERS docs/CLAUDE.md pyproject.toml docs/launch/*.md </dev/null
git add -A
git commit -m "refactor(launch): move the catalog to docs/launch

The launch page is a page of the docs site, so its source belongs in the
docs tree. Removes the need for a watch: key and a paths-filter entry,
since docs_dir is already watched and already triggers the deploy.

Adds exclude_docs so the build inputs are not served next to the output,
a CODEOWNERS line preserving analytics-engineers ownership, and widens
the stated scope in docs/CLAUDE.md. Deletes views.yml, which the design
retired. Declares pyyaml, which resolved only transitively.

Refs #4818"
```

---

### Task 2: `build.py` skeleton — `load()` and `CatalogError`

**Files:**

- Create: `docs/launch/build.py`, `docs/launch/groups.yml`,
  `docs/launch/template.html`
- Create: `tests/launch/conftest.py`, `tests/launch/test_load.py`

**Interfaces:**

- Consumes: `docs/launch/links.yml` from Task 1.
- Produces: `Catalog` (frozen dataclass with `.entries: list[dict]`,
  `.config: dict`, `.template: str`), `load(root: Path = HERE) -> Catalog`,
  `CatalogError(errors: list[str])` with an `.errors` attribute.

- [ ] **Step 1: Make the module importable from tests**

`docs/launch` is not a package and `docs` is not on `sys.path`. Create
`tests/launch/conftest.py`:

```python
"""Put `docs/` on sys.path so tests can `import launch.build`.

docs/launch has no __init__.py and does not need one — it resolves as a
PEP 420 namespace package. Scoped to this directory so the other 749
collected tests are unaffected.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "docs"))
```

- [ ] **Step 2: Write the failing test**

`tests/launch/test_load.py`:

```python
from launch.build import Catalog, load


def test_load_reads_the_three_sources(tmp_path):
    (tmp_path / "links.yml").write_text("- id: a\n  name: A\n")
    (tmp_path / "groups.yml").write_text("groups: []\nfamilies: []\npromos: []\n")
    (tmp_path / "template.html").write_text("<p>__CATALOG__</p>")

    catalog = load(tmp_path)

    assert isinstance(catalog, Catalog)
    assert catalog.entries == [{"id": "a", "name": "A"}]
    assert catalog.config["groups"] == []
    assert "__CATALOG__" in catalog.template


def test_load_defaults_to_the_real_catalog():
    catalog = load()
    assert len(catalog.entries) > 30
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest tests/launch/test_load.py -v` Expected: FAIL,
`ModuleNotFoundError: No module named 'launch'`

- [ ] **Step 4: Write `build.py`**

```python
"""Render the staff launch page from the catalog in this directory.

Four functions, in order: load, select, validate, render. Nothing here
writes to the filesystem — render() returns a string and the MkDocs hook
decides where it goes. That is what keeps the tests free of temp files
and what stops `mkdocs serve` rebuilding itself in a loop.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent

ID_RE = re.compile(r"^[a-z0-9_]+$")

# The nine values documented in README.md, mapped to display labels.
SYSTEMS = {
    "tableau": "Tableau",
    "appsheet": "AppSheet",
    "zendesk": "Zendesk",
    "google-sheet": "Google Sheet",
    "google-slides": "Google Slides",
    "google-form": "Google Form",
    "google-doc": "Google Doc",
    "apps-script": "Apps Script",
    "other": "Other",
}

STATUSES = {"needs-review", "verified"}
AUDIENCES = {"teachers", "leaders", "ops", "region"}

# Region accents come from the KIPP NJ | Miami design system. `all` is a
# legal value on a normal entry but never on a family member.
REGIONS = {
    "newark": ("Newark", "var(--kipp-blue)"),
    "camden": ("Camden", "var(--kipp-green)"),
    "miami": ("Miami", "var(--kipp-orange)"),
    "paterson": ("Paterson", "var(--kipp-red)"),
}
REGION_VALUES = set(REGIONS) | {"all"}


class CatalogError(Exception):
    """Every validation problem found, not just the first one."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(
            f"{len(errors)} problem(s) in the launch catalog:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )


@dataclass(frozen=True)
class Catalog:
    entries: list[dict]
    config: dict
    template: str


def load(root: Path = HERE) -> Catalog:
    """Read links.yml, groups.yml and template.html from `root`."""
    entries = yaml.safe_load((root / "links.yml").read_text()) or []
    config = yaml.safe_load((root / "groups.yml").read_text()) or {}
    template = (root / "template.html").read_text()
    return Catalog(entries=entries, config=config, template=template)
```

- [ ] **Step 5: Create `docs/launch/groups.yml`**

Group definitions, families, promos and the threshold. No `assignments` map —
`group` goes on each entry in Task 5.

Four of the prototype's five promo cards pointed at `#`. Tier 1 rejects those,
and the spec's default is to drop them rather than invent URLs, so only the one
with a real destination ships:

```yaml
# Presentation data the catalog itself does not carry.

# Below this many verified entries, no page is generated at all. The URL
# 404s rather than serving a near-empty page. Owned by the catalog owner.
minimum_verified: 25

groups:
  - id: attendance
    name: Attendance & behavior
  - id: academics
    name: Academics & assessment
  - id: college
    name: College readiness & pathways
  - id: performance
    name: Performance management & coaching
  - id: staff
    name: Staff, hiring & pay
  - id: operations
    name: Enrollment & operations
  - id: surveys
    name: Surveys

# Region-variant tools collapse into one row with per-region sub-links.
# Members are matched on `name`; each must carry exactly one region.
families:
  - id: gpa_roster
    name: GPA Roster
    description: Course grades and GPA by student. One sheet per region.
    group: academics
    members:
      - "GPA Roster: Camden"
      - "GPA Roster: Miami"
      - "GPA Roster: Newark"
  - id: student_contact_info_feed
    name: Student Contact Info Feed
    description: Student and guardian contact information. Pick your region.
    group: operations
    members:
      - Student Contact Info Feed - KIPP Newark
      - Student Contact Info Feed - KIPP Camden
      - Student Contact Info Feed - KIPP Miami
      - Student Contact Info Feed - KIPP Paterson

# "From the data team" cards, pointing at prose that lives in Zendesk.
promos:
  - label: All help guides
    blurb: Every written guide in one list.
    url: https://teamschools.zendesk.com/hc/en-us/categories/204269047-Data-Launch
```

- [ ] **Step 6: Copy the template in**

Copy `.claude/scratch/launch-prototype/template.html` to
`docs/launch/template.html`, then make one edit — remove the three
`fonts.googleapis.com` / `fonts.gstatic.com` `<link>` tags and replace the brand
font declaration:

```css
--font-brand:
  "Whitney SSm A", "Whitney", Calibri, "Segoe UI", system-ui, -apple-system,
  "Helvetica Neue", Arial, sans-serif;
```

A staff page should not reach a third party for a typeface, and Whitney is the
KTAF brand face with Calibri as the documented fallback.

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/launch/test_load.py -v` Expected: 2 passed.

- [ ] **Step 8: Commit**

```bash
git add docs/launch/build.py docs/launch/groups.yml docs/launch/template.html \
  tests/launch/conftest.py tests/launch/test_load.py
git commit -m "feat(launch): add the build module skeleton and its sources

load() reads the three files from a directory rather than from git, so
it works under a shallow CI checkout and reads the tree it is given.

Drops four promo cards that pointed at '#'; a card linking nowhere is
worse than no card. Drops the Google Fonts CDN in favour of the Whitney
and Calibri stack.

Refs #4818"
```

---

### Task 3: `validate()` tier 1 — structural rules

**Files:**

- Modify: `docs/launch/build.py`
- Create: `tests/launch/test_validate.py`

**Interfaces:**

- Consumes: `Catalog`, `CatalogError` from Task 2.
- Produces: `validate(catalog: Catalog, verified: list[dict]) -> list[str]` —
  returns error strings, does not raise. Tier 2 is added in Task 4; this task
  passes `verified=[]`.

- [ ] **Step 1: Write the failing tests**

`tests/launch/test_validate.py`:

```python
import pytest

from launch.build import Catalog, validate

GOOD_ENTRY = {
    "id": "attendance_dashboard",
    "name": "Attendance Dashboard",
    "url": "https://tableau.kipp.org/t/KIPPNJ/views/Attendance",
    "system": "tableau",
    "status": "needs-review",
}

GOOD_CONFIG = {
    "minimum_verified": 25,
    "groups": [{"id": "attendance", "name": "Attendance & behavior"}],
    "families": [],
    "promos": [{"label": "Guides", "blurb": "All of them", "url": "https://x.test"}],
}


def make_catalog(entries=None, config=None) -> Catalog:
    return Catalog(
        entries=[dict(GOOD_ENTRY)] if entries is None else entries,
        config=GOOD_CONFIG if config is None else config,
        template="__CATALOG__",
    )


def test_a_clean_catalog_has_no_errors():
    assert validate(make_catalog(), []) == []


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        ({"id": None}, "id"),
        ({"id": "Not Valid"}, "id"),
        ({"name": ""}, "name"),
        ({"url": "http://insecure.test"}, "https"),
        ({"url": None}, "url"),
        ({"system": "notion"}, "system"),
        ({"status": "reviewed"}, "status"),
        ({"access": "open"}, "access"),
        ({"regions": ["brooklyn"]}, "region"),
    ],
)
def test_tier_one_rejects_bad_fields(mutate, fragment):
    entry = {**GOOD_ENTRY, **mutate}
    errors = validate(make_catalog(entries=[entry]), [])
    assert any(fragment in e for e in errors), errors


def test_duplicate_ids_are_rejected():
    errors = validate(make_catalog(entries=[dict(GOOD_ENTRY), dict(GOOD_ENTRY)]), [])
    assert any("duplicate" in e for e in errors)


def test_entries_must_be_a_list_of_mappings():
    errors = validate(make_catalog(entries=["just a string"]), [])
    assert any("mapping" in e for e in errors)


def test_missing_groups_key_is_rejected():
    errors = validate(make_catalog(config={"groups": [], "families": []}), [])
    assert any("promos" in e for e in errors)


def test_family_naming_a_missing_entry_is_rejected():
    config = {
        **GOOD_CONFIG,
        "families": [
            {
                "id": "f",
                "name": "F",
                "description": "d",
                "group": "attendance",
                "members": ["Nonexistent Tool"],
            }
        ],
    }
    errors = validate(make_catalog(config=config), [])
    assert any("Nonexistent Tool" in e for e in errors)


def test_family_with_an_unknown_group_is_rejected():
    config = {
        **GOOD_CONFIG,
        "families": [
            {
                "id": "f",
                "name": "F",
                "description": "d",
                "group": "nope",
                "members": ["Attendance Dashboard"],
            }
        ],
    }
    errors = validate(make_catalog(config=config), [])
    assert any("nope" in e for e in errors)


def test_promo_pointing_nowhere_is_rejected():
    config = {**GOOD_CONFIG, "promos": [{"label": "X", "blurb": "y", "url": "#"}]}
    errors = validate(make_catalog(config=config), [])
    assert any("promo" in e for e in errors)


def test_every_problem_is_reported_not_just_the_first():
    entry = {**GOOD_ENTRY, "id": "BAD", "system": "notion", "url": "http://x.test"}
    errors = validate(make_catalog(entries=[entry]), [])
    assert len(errors) >= 3
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/launch/test_validate.py -v` Expected: FAIL,
`ImportError: cannot import name 'validate'`

- [ ] **Step 3: Implement tier 1**

Append to `docs/launch/build.py`:

```python
def _tier_one(catalog: Catalog) -> list[str]:
    errors: list[str] = []
    entries = catalog.entries
    config = catalog.config

    if not isinstance(entries, list):
        return ["links.yml must be a list of entries"]

    seen: set[str] = set()
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"links.yml entry {i} is not a mapping")
            continue

        where = entry.get("name") or entry.get("id") or f"entry {i}"

        entry_id = entry.get("id")
        if not entry_id:
            errors.append(f"{where}: missing `id`")
        elif not ID_RE.match(str(entry_id)):
            errors.append(f"{where}: `id` {entry_id!r} must match ^[a-z0-9_]+$")
        elif entry_id in seen:
            errors.append(f"{where}: duplicate `id` {entry_id!r}")
        else:
            seen.add(entry_id)

        if not (entry.get("name") or "").strip():
            errors.append(f"{where}: missing `name`")

        url = entry.get("url")
        if not url:
            errors.append(f"{where}: missing `url`")
        elif not str(url).startswith("https://"):
            errors.append(f"{where}: `url` must be https")

        system = entry.get("system")
        if system not in SYSTEMS:
            errors.append(f"{where}: unknown `system` {system!r}")

        status = entry.get("status")
        if status not in STATUSES:
            errors.append(f"{where}: `status` must be one of {sorted(STATUSES)}")

        access = entry.get("access")
        if access is not None and access != "limited":
            errors.append(f"{where}: `access` may only be 'limited', got {access!r}")

        for region in entry.get("regions") or []:
            if region not in REGION_VALUES:
                errors.append(f"{where}: unknown region {region!r}")

    for key in ("groups", "families", "promos"):
        if key not in config:
            errors.append(f"groups.yml is missing the `{key}` key")

    group_ids = {g["id"] for g in config.get("groups") or []}
    names = {e.get("name") for e in entries if isinstance(e, dict)}

    for family in config.get("families") or []:
        if family.get("group") not in group_ids:
            errors.append(
                f"family {family.get('id')!r} names unknown group "
                f"{family.get('group')!r}"
            )
        for member in family.get("members") or []:
            if member not in names:
                errors.append(
                    f"family {family.get('id')!r} names missing tool {member!r}"
                )

    for promo in config.get("promos") or []:
        url = (promo.get("url") or "").strip()
        if not url or url == "#":
            errors.append(f"promo {promo.get('label')!r} has no destination")

    return errors


def validate(catalog: Catalog, verified: list[dict]) -> list[str]:
    """Tier 1 over everything; tier 2 over the verified subset."""
    return _tier_one(catalog)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/launch/test_validate.py -v` Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add docs/launch/build.py tests/launch/test_validate.py
git commit -m "feat(launch): add tier 1 structural validation

Applies to every entry regardless of status, so a duplicate id or a
non-https url is caught while an entry is still being drafted. Errors
accumulate rather than short-circuiting.

Refs #4818"
```

---

### Task 4: `select()` and tier 2 — publish-readiness rules

**Files:**

- Modify: `docs/launch/build.py`, `tests/launch/test_validate.py`
- Create: `tests/launch/test_select.py`

**Interfaces:**

- Consumes: `Catalog`, `validate` from Task 3.
- Produces: `select(catalog: Catalog) -> list[dict]` returning entries whose
  `status == "verified"`, in catalog order. `validate` now applies tier 2 to the
  list passed as `verified`.

`select()` has no threshold awareness. The threshold is checked in `render()` so
that validation always runs in full, including below it.

- [ ] **Step 1: Write the failing tests**

`tests/launch/test_select.py`:

```python
from launch.build import Catalog, select


def catalog(*statuses) -> Catalog:
    return Catalog(
        entries=[
            {"id": f"t{i}", "name": f"T{i}", "status": s}
            for i, s in enumerate(statuses)
        ],
        config={},
        template="",
    )


def test_select_keeps_only_verified():
    got = select(catalog("verified", "needs-review", "verified"))
    assert [e["id"] for e in got] == ["t0", "t2"]


def test_select_preserves_catalog_order():
    got = select(catalog("verified", "verified", "verified"))
    assert [e["id"] for e in got] == ["t0", "t1", "t2"]


def test_select_returns_empty_when_nothing_is_verified():
    assert select(catalog("needs-review", "needs-review")) == []
```

Append to `tests/launch/test_validate.py`:

```python
VERIFIED = {
    **GOOD_ENTRY,
    "status": "verified",
    "description": "Monitor ADA and chronic absenteeism.",
    "audiences": ["leaders", "ops"],
}


def test_tier_two_passes_a_complete_verified_entry():
    assert validate(make_catalog(entries=[VERIFIED]), [VERIFIED]) == []


def test_tier_two_requires_a_description():
    entry = {**VERIFIED, "description": "  "}
    errors = validate(make_catalog(entries=[entry]), [entry])
    assert any("description" in e for e in errors)


def test_tier_two_requires_audiences():
    entry = {**VERIFIED, "audiences": []}
    errors = validate(make_catalog(entries=[entry]), [entry])
    assert any("audiences" in e for e in errors)


def test_tier_two_rejects_an_unknown_audience():
    entry = {**VERIFIED, "audiences": ["parents"]}
    errors = validate(make_catalog(entries=[entry]), [entry])
    assert any("parents" in e for e in errors)


def test_tier_two_requires_https_on_a_guide():
    entry = {**VERIFIED, "guide": "http://guide.test"}
    errors = validate(make_catalog(entries=[entry]), [entry])
    assert any("guide" in e for e in errors)


def test_tier_two_is_not_applied_to_unverified_entries():
    draft = {**GOOD_ENTRY, "description": "", "audiences": []}
    assert validate(make_catalog(entries=[draft]), []) == []


def test_family_member_needs_exactly_one_real_region():
    member = {
        **VERIFIED,
        "id": "gpa_roster_camden",
        "name": "GPA Roster: Camden",
        "regions": ["all"],
    }
    config = {
        **GOOD_CONFIG,
        "families": [
            {
                "id": "gpa_roster",
                "name": "GPA Roster",
                "description": "d",
                "group": "attendance",
                "members": ["GPA Roster: Camden"],
            }
        ],
    }
    errors = validate(make_catalog(entries=[member], config=config), [member])
    assert any("region" in e for e in errors)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/launch/ -v` Expected: FAIL —
`cannot import name 'select'`, and the tier 2 tests fail because `validate`
ignores its `verified` argument.

- [ ] **Step 3: Implement**

Add to `docs/launch/build.py`, and replace `validate`:

```python
def select(catalog: Catalog) -> list[dict]:
    """Entries that publish. Partitions only — never short-circuits."""
    return [
        e
        for e in catalog.entries
        if isinstance(e, dict) and e.get("status") == "verified"
    ]


def _tier_two(catalog: Catalog, verified: list[dict]) -> list[str]:
    errors: list[str] = []
    family_members = {
        member
        for family in catalog.config.get("families") or []
        for member in family.get("members") or []
    }

    for entry in verified:
        where = entry.get("name") or entry.get("id") or "<unnamed>"

        if not (entry.get("description") or "").strip():
            errors.append(f"{where}: verified entries need a `description`")

        audiences = entry.get("audiences") or []
        if not audiences:
            errors.append(f"{where}: verified entries need at least one audience")
        for audience in audiences:
            if audience not in AUDIENCES:
                errors.append(f"{where}: unknown audience {audience!r}")

        guide = entry.get("guide")
        if guide and not str(guide).startswith("https://"):
            errors.append(f"{where}: `guide` must be https")

        if entry.get("name") in family_members:
            regions = entry.get("regions") or []
            if len(regions) != 1 or regions[0] not in REGIONS:
                errors.append(
                    f"{where}: a family member needs exactly one region "
                    f"from {sorted(REGIONS)}, got {regions!r}"
                )

    return errors


def validate(catalog: Catalog, verified: list[dict]) -> list[str]:
    """Tier 1 over everything; tier 2 over the verified subset."""
    return _tier_one(catalog) + _tier_two(catalog, verified)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/launch/ -v` Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add docs/launch/build.py tests/launch/test_select.py \
  tests/launch/test_validate.py
git commit -m "feat(launch): add select() and tier 2 publish-readiness rules

select() partitions and never exits, so validation runs in full below
the publication threshold. Tier 2 applies only to verified entries: a
half-finished draft never blocks a commit, but flipping one to verified
while it lacks a description does.

Refs #4818"
```

---

### Task 5: Put `group` on every entry

**Files:**

- Modify: `docs/launch/links.yml` (44 entries), `docs/launch/build.py`,
  `tests/launch/test_validate.py`

**Interfaces:**

- Consumes: `_tier_one` from Task 3.
- Produces: every entry in `links.yml` carries `group: <id>` matching a
  `groups.yml` id. Tier 1 enforces it.

The spec deferred this. That deferral assumed 37 entries in flight on #4767 and
a page that would not publish for months. Both are now false — see the note at
the top of this plan.

- [ ] **Step 1: Add the field to all 44 entries**

Write and run this script. It asserts a complete mapping before writing, so a
missed entry aborts rather than producing a half-annotated file.

```python
# .claude/scratch/add-groups.py
import re
from pathlib import Path

import yaml

LINKS = Path("/workspaces/teamster/.worktrees/launch-build-pipeline/docs/launch/links.yml")

GROUPS = {
    "Attendance Dashboard": "attendance",
    "OKRTS Dashboard": "attendance",
    "DDI Suite": "academics",
    "Gradebook and GPA Dashboard": "academics",
    "LIT Dashboard": "academics",
    "FAST & iReady Data Tool (MIA)": "academics",
    "i-Ready APM Tool": "academics",
    "State Testing Analysis Tool": "academics",
    "Testing Accommodations": "academics",
    "GPA Roster: Camden": "academics",
    "GPA Roster: Miami": "academics",
    "GPA Roster: Newark": "academics",
    "High School Early Warning": "college",
    "College Admission Readiness Assessment Tracker (CARAT)": "college",
    "Promotional Status Dashboard": "college",
    "KIPP Forward Data Suite": "college",
    "Coaching Conversation Tool": "performance",
    "Grow Dashboard": "performance",
    "Leader PM Dashboard": "performance",
    "Leader PM App": "performance",
    "Teacher Development Dashboard": "performance",
    "Certification Dashboard": "performance",
    "Content Team (MIA)": "performance",
    "Operations Systems": "performance",
    "Staff Roster": "staff",
    "Recruitment Dashboard": "staff",
    "Seat Tracker": "staff",
    "FRESH Dashboard": "staff",
    "Staff Attrition Dashboard": "staff",
    "Staff Demographic Explorer": "staff",
    "Staff Recent Job & Salary Changes": "staff",
    "Finance & Accounting Tools": "staff",
    "Stipend and Bonus Dashboard": "staff",
    "Stipend App": "staff",
    "Ops Dashboard": "operations",
    "Data Quality Dashboard": "operations",
    "Zendesk Dashboard": "operations",
    "Student Contact Info Feed - KIPP Newark": "operations",
    "Student Contact Info Feed - KIPP Camden": "operations",
    "Student Contact Info Feed - KIPP Miami": "operations",
    "Student Contact Info Feed - KIPP Paterson": "operations",
    "Survey HQ": "surveys",
    "Survey Dashboard": "surveys",
    "Manager Survey Report": "surveys",
}

text = LINKS.read_text()
entries = yaml.safe_load(text)
names = {e["name"] for e in entries}

missing = names - set(GROUPS)
stale = set(GROUPS) - names
assert not missing, f"no group for: {sorted(missing)}"
assert not stale, f"group for tools not in the catalog: {sorted(stale)}"

# Insert `group:` immediately after each `system:` line, preserving all
# comments and formatting elsewhere in the file.
out, idx = [], 0
for line in text.splitlines(keepends=True):
    out.append(line)
    if line.startswith("  system:"):
        out.append(f"  group: {GROUPS[entries[idx]['name']]}\n")
        idx += 1
assert idx == len(entries), f"patched {idx} of {len(entries)} entries"
LINKS.write_text("".join(out))
print(f"added `group` to {idx} entries")
```

Run: `uv run --with pyyaml --no-project python .claude/scratch/add-groups.py`
Expected: `added \`group\` to 44 entries`

- [ ] **Step 2: Write the failing test**

Append to `tests/launch/test_validate.py`:

```python
def test_tier_one_requires_a_known_group():
    entry = {**GOOD_ENTRY, "group": "nonexistent"}
    errors = validate(make_catalog(entries=[entry]), [])
    assert any("group" in e for e in errors)


def test_tier_one_requires_group_to_be_present():
    entry = {k: v for k, v in GOOD_ENTRY.items()}
    entry.pop("group", None)
    errors = validate(make_catalog(entries=[entry]), [])
    assert any("group" in e for e in errors)
```

Also add `"group": "attendance"` to the `GOOD_ENTRY` dict at the top of the
file, so the existing tests keep passing.

- [ ] **Step 3: Run to verify the new tests fail**

Run: `uv run pytest tests/launch/test_validate.py -v` Expected: the two new
tests FAIL; the rest pass.

- [ ] **Step 4: Enforce it in tier 1**

In `_tier_one`, the `group_ids` set is currently computed after the entry loop.
Move it above the loop, then add inside the loop, after the `regions` check:

```python
        group = entry.get("group")
        if not group:
            errors.append(f"{where}: missing `group`")
        elif group not in group_ids:
            errors.append(f"{where}: unknown `group` {group!r}")
```

- [ ] **Step 5: Run everything**

Run: `uv run pytest tests/launch/ -v` Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add docs/launch/links.yml docs/launch/build.py tests/launch/test_validate.py
git commit -m "feat(launch): put the topical group on each catalog entry

The spec deferred this behind #4767, which has since merged, and behind
a threshold the catalog has already crossed -- 39 of 44 entries are
verified against a minimum of 25, so the page publishes on the next
deploy. Shipping a flat alphabetical list to staff and grouping it
afterwards is worse than grouping it now.

Replaces the prototype's name-keyed side table, which had to stay
exhaustive and broke twice during the verification pass when a tool was
renamed and another removed.

Refs #4818"
```

---

### Task 6: `render()` — grouping, families, threshold, escaping

**Files:**

- Modify: `docs/launch/build.py`
- Create: `tests/launch/test_render.py`

**Interfaces:**

- Consumes: `Catalog`, `select`, `validate` from Tasks 2–5.
- Produces:
  - `render(catalog: Catalog, verified: list[dict], updated: str | None = None) -> str | None`
    — `None` when `len(verified) < config["minimum_verified"]`, otherwise the
    full HTML page.
  - `build(root: Path = HERE, updated: str | None = None) -> str | None` — the
    single entry point the hook calls. Raises `CatalogError` if validation
    fails.

- [ ] **Step 1: Write the failing tests**

`tests/launch/test_render.py`:

```python
import json
import re

import pytest

from launch.build import Catalog, CatalogError, build, render

CONFIG = {
    "minimum_verified": 2,
    "groups": [
        {"id": "attendance", "name": "Attendance & behavior"},
        {"id": "academics", "name": "Academics & assessment"},
    ],
    "families": [],
    "promos": [{"label": "Guides", "blurb": "All", "url": "https://x.test"}],
}

TEMPLATE = "<html><script>const CATALOG = __CATALOG__;</script></html>"


def entry(**over):
    base = {
        "id": "t",
        "name": "T",
        "url": "https://x.test",
        "system": "tableau",
        "status": "verified",
        "group": "attendance",
        "description": "d",
        "audiences": ["ops"],
    }
    return {**base, **over}


def catalog(entries, config=None):
    return Catalog(entries=entries, config=config or CONFIG, template=TEMPLATE)


def payload(html):
    match = re.search(r"const CATALOG = (\{.*\});", html, re.S)
    return json.loads(match.group(1))


def test_below_threshold_renders_nothing():
    one = [entry(id="a", name="A")]
    assert render(catalog(one), one) is None


def test_at_threshold_renders_a_page():
    two = [entry(id="a", name="A"), entry(id="b", name="B")]
    assert render(catalog(two), two) is not None


def test_only_verified_entries_reach_the_payload():
    entries = [
        entry(id="a", name="A"),
        entry(id="b", name="B"),
        entry(id="c", name="C", status="needs-review"),
    ]
    verified = [e for e in entries if e["status"] == "verified"]
    got = payload(render(catalog(entries), verified))
    assert [t["id"] for t in got["tools"]] == ["a", "b"]


def test_a_closing_script_tag_cannot_escape_the_payload():
    entries = [
        entry(id="a", name="A", description="</script><img src=x onerror=alert(1)>"),
        entry(id="b", name="B"),
    ]
    html = render(catalog(entries), entries)
    assert "</script><img" not in html
    assert "\\u003c/script" in html
    assert payload(html)["tools"][0]["description"].startswith("</script>")


def test_the_limited_badge_needs_the_exact_value():
    entries = [
        entry(id="a", name="A", access="limited"),
        entry(id="b", name="B", description="limited access is mentioned here"),
    ]
    got = payload(render(catalog(entries), entries))
    by_id = {t["id"]: t for t in got["tools"]}
    assert by_id["a"]["limited"] is True
    assert by_id["b"]["limited"] is False


def test_family_members_carry_a_region_label_and_colour():
    config = {
        **CONFIG,
        "families": [
            {
                "id": "f",
                "name": "Fam",
                "description": "d",
                "group": "academics",
                "members": ["A", "B"],
            }
        ],
    }
    entries = [
        entry(id="a", name="A", regions=["camden"]),
        entry(id="b", name="B", regions=["miami"]),
    ]
    got = payload(render(catalog(entries, config), entries))
    labels = {t["id"]: t["regionLabel"] for t in got["tools"]}
    assert labels == {"a": "Camden", "b": "Miami"}
    assert all(t["family"]["id"] == "f" for t in got["tools"])


def test_unknown_system_falls_back_to_the_raw_value():
    entries = [entry(id="a", name="A", system="google-doc"), entry(id="b", name="B")]
    got = payload(render(catalog(entries), entries))
    assert got["tools"][0]["systemLabel"] == "Google Doc"


def test_a_missing_date_does_not_fail_the_build(tmp_path):
    # tmp_path is not a git repo, so _updated() must swallow the failure.
    (tmp_path / "links.yml").write_text(
        "- id: a\n  name: A\n  url: https://x.test\n  system: tableau\n"
        "  status: verified\n  group: attendance\n  description: d\n"
        "  audiences: [ops]\n"
        "- id: b\n  name: B\n  url: https://x.test\n  system: tableau\n"
        "  status: verified\n  group: attendance\n  description: d\n"
        "  audiences: [ops]\n"
    )
    (tmp_path / "groups.yml").write_text(
        "minimum_verified: 2\n"
        "groups:\n  - id: attendance\n    name: Attendance\n"
        "families: []\n"
        "promos:\n  - label: G\n    blurb: b\n    url: https://x.test\n"
    )
    (tmp_path / "template.html").write_text(TEMPLATE)

    html = build(tmp_path)

    assert html is not None
    assert payload(html)["meta"]["updated"] == ""


def test_build_raises_with_every_problem_listed(tmp_path):
    (tmp_path / "links.yml").write_text(
        "- id: BAD\n  name: X\n  url: http://x\n  system: notion\n  status: nope\n"
    )
    (tmp_path / "groups.yml").write_text("groups: []\nfamilies: []\npromos: []\n")
    (tmp_path / "template.html").write_text(TEMPLATE)

    with pytest.raises(CatalogError) as excinfo:
        build(tmp_path)

    assert len(excinfo.value.errors) >= 4
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/launch/test_render.py -v` Expected: FAIL,
`cannot import name 'render'`

- [ ] **Step 3: Implement**

Append to `docs/launch/build.py`:

```python
def _tool(entry: dict, family: dict | None) -> dict:
    regions = entry.get("regions") or []
    label, colour = REGIONS.get(regions[0], ("", "")) if regions else ("", "")
    return {
        "id": entry["id"],
        "name": entry["name"],
        "url": entry["url"],
        "description": (entry.get("description") or "").strip(),
        "audiences": entry.get("audiences") or [],
        "system": entry["system"],
        "systemLabel": SYSTEMS.get(entry["system"], entry["system"]),
        "group": entry["group"],
        "guide": entry.get("guide"),
        "regionLabel": label,
        "regionColor": colour,
        "limited": entry.get("access") == "limited",
        "family": (
            {
                "id": family["id"],
                "name": family["name"],
                "description": family["description"],
                "group": family["group"],
            }
            if family
            else None
        ),
    }


def render(
    catalog: Catalog, verified: list[dict], updated: str | None = None
) -> str | None:
    """The page, or None when too little of the catalog is verified."""
    minimum = catalog.config.get("minimum_verified", 0)
    if len(verified) < minimum:
        return None

    member_of = {
        member: family
        for family in catalog.config.get("families") or []
        for member in family.get("members") or []
    }

    payload = {
        "tools": [_tool(e, member_of.get(e["name"])) for e in verified],
        "groups": catalog.config["groups"],
        "views": [{"id": i, "label": lbl} for i, lbl in VIEWS],
        "systems": [
            {"id": i, "label": lbl}
            for i, lbl in SYSTEMS.items()
            if any(e["system"] == i for e in verified)
        ],
        "promos": catalog.config["promos"],
        "meta": {"updated": updated or "", "count": len(verified)},
    }

    # json.dumps escapes quotes and control characters but NOT `<`, so a
    # value containing a closing script tag would end the block early and
    # blank the page with an exit-zero build. Escaping at the unicode
    # level keeps the JSON valid.
    encoded = (
        json.dumps(payload, indent=1)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    return catalog.template.replace("__CATALOG__", encoded)


def _updated(root: Path) -> str:
    """Tip-commit date, or empty when git cannot answer.

    Deliberately not path-filtered: `git log -1 -- <path>` returns empty
    under actions/checkout's shallow clone, while the unfiltered tip
    resolves at depth 1. A missing date is not worth failing a build for,
    so every failure mode returns "" and the template omits the stamp.
    """
    try:
        return subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "log",
                "-1",
                "--format=%ad",
                "--date=format:%-d %b %Y",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return ""


def build(root: Path = HERE, updated: str | None = None) -> str | None:
    """Load, validate and render. Raises CatalogError on any problem."""
    catalog = load(root)
    verified = select(catalog)
    errors = validate(catalog, verified)
    if errors:
        raise CatalogError(errors)
    return render(catalog, verified, updated or _updated(root))
```

Add `import json` and `import subprocess` to the imports, and this constant
beside `SYSTEMS`:

```python
VIEWS = [
    ("all", "All tools"),
    ("teachers", "Teachers"),
    ("leaders", "Leaders"),
    ("ops", "Operations"),
    ("region", "Regional & CMO"),
]
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/launch/ -v` Expected: all pass.

- [ ] **Step 5: Render the real catalog and open it**

```bash
cd /workspaces/teamster/.worktrees/launch-build-pipeline
uv run --with pyyaml --no-project python -c "
import sys; sys.path.insert(0, 'docs')
from launch.build import build
html = build()
print('suppressed' if html is None else f'{len(html)} bytes')
open('/tmp/launch-preview.html','w').write(html or '')
"
```

Expected: a byte count, not `suppressed` — 39 verified is above the minimum
of 25. Open `/tmp/launch-preview.html` and confirm the groups render, the GPA
Roster and Contact Info rows collapse with region buttons, and the counts look
right.

- [ ] **Step 6: Commit**

```bash
git add docs/launch/build.py tests/launch/test_render.py
git commit -m "feat(launch): render the page, grouped, with a threshold

render() returns a string and never writes a file, which is what keeps
mkdocs serve from rebuilding itself in a loop and what lets every test
run on in-memory data.

Below minimum_verified it returns None: no page rather than a near-empty
one. The threshold is checked here, after validation has run in full,
so the pre-launch window still has a structural gate.

Pins the script-tag escaping: json.dumps does not escape '<', so a
catalog value containing a closing script tag would blank the page with
an exit-zero build.

Refs #4818"
```

---

### Task 7: Guard the real catalog

**Files:**

- Create: `tests/launch/test_catalog.py`

**Interfaces:**

- Consumes: `load`, `select`, `validate` from Tasks 2–5.
- Produces: nothing. This is the test that actually protects `main`.

- [ ] **Step 1: Write the test**

```python
"""The real catalog must always be valid. This is the test that protects main.

The others prove the rules work; this one proves the data obeys them.
"""

from launch.build import load, select, validate


def test_the_real_catalog_is_valid():
    catalog = load()
    errors = validate(catalog, select(catalog))
    assert errors == [], "\n".join(errors)


def test_the_real_catalog_is_not_accidentally_empty():
    # Guards against a path regression silently passing the test above.
    assert len(load().entries) > 30


def test_every_family_member_resolves():
    catalog = load()
    names = {e["name"] for e in catalog.entries}
    for family in catalog.config["families"]:
        for member in family["members"]:
            assert member in names, f"{family['id']} names missing {member!r}"
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/launch/test_catalog.py -v` Expected: 3 passed. If
`test_the_real_catalog_is_valid` fails, the failure message lists every problem
— fix the data, not the test.

- [ ] **Step 3: Commit**

```bash
git add tests/launch/test_catalog.py
git commit -m "test(launch): assert the real catalog passes validation

The rule tests prove the rules work. This one proves the data obeys
them, and is what stops a bad merge reaching the docs build.

Refs #4818"
```

---

### Task 8: Generate the page from an MkDocs hook

**Files:**

- Modify: `docs/hooks.py`
- Create: `tests/launch/test_hook.py`

**Interfaces:**

- Consumes: `build()` from Task 6.
- Produces: an `on_files` hook that adds `launch/index.html` to the MkDocs file
  set via `File.generated`.

`on_files`, not `on_pre_build`: writing into `docs_dir` during a build makes
`mkdocs serve` re-detect its own write and rebuild about twice a second,
indefinitely. `File.generated` registers a virtual file that never touches
`docs_dir`.

- [ ] **Step 1: Write the failing test**

`tests/launch/test_hook.py`:

```python
"""The hook is thin, so this checks wiring rather than behaviour."""

import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"


def load_hooks():
    sys.path.insert(0, str(DOCS))
    import hooks

    return hooks


def test_hooks_exposes_on_files():
    assert callable(load_hooks().on_files)


def test_hooks_still_hides_nav_on_the_homepage():
    assert callable(load_hooks().on_page_markdown)


def test_generated_page_lands_in_the_file_set():
    from mkdocs.config.defaults import MkDocsConfig

    config = MkDocsConfig()
    config.load_dict({"site_name": "t", "docs_dir": str(DOCS)})
    assert config.validate()[0] == []

    from mkdocs.structure.files import Files

    files = load_hooks().on_files(Files([]), config)
    assert any(f.src_uri == "launch/index.html" for f in files)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/launch/test_hook.py -v` Expected: FAIL,
`module 'hooks' has no attribute 'on_files'`

- [ ] **Step 3: Implement**

Replace `docs/hooks.py` entirely:

```python
"""MkDocs hooks.

Two jobs: hide the nav on the homepage, and generate the staff launch
page from the catalog in `launch/`.

The generated page is registered with `File.generated` rather than
written into `docs_dir`. Writing there during a build makes the dev
server re-detect its own write and rebuild about twice a second forever.
"""

import importlib
import sys
from pathlib import Path

from mkdocs.structure.files import File

# `launch` is a PEP 420 namespace package under docs/. Anchored on
# __file__ rather than cwd, because `mkdocs build -f <path>` is supported.
sys.path.insert(0, str(Path(__file__).resolve().parent))


def on_page_markdown(markdown, page, config, files):
    if page.file.src_path == "README.md":
        page.meta["hide"] = ["navigation", "toc"]
    return markdown


def on_files(files, config):
    # Reload when already imported: the dev server is a long-running
    # process, so an edit to build.py would otherwise be invisible until
    # restart. load() re-reads the YAML every call, so catalog edits are
    # picked up regardless.
    if "launch.build" in sys.modules:
        launch_build = importlib.reload(sys.modules["launch.build"])
    else:
        from launch import build as launch_build

    html = launch_build.build()
    if html is None:
        return files

    files.append(File.generated(config, "launch/index.html", content=html))
    return files
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/launch/ -v` Expected: all pass.

- [ ] **Step 5: Verify end to end**

```bash
cd /workspaces/teamster/.worktrees/launch-build-pipeline
uv run --group docs mkdocs build --site-dir /tmp/launch-site
ls -la /tmp/launch-site/launch/
grep -c 'const CATALOG' /tmp/launch-site/launch/index.html
grep -c 'launch/index.html' /tmp/launch-site/sitemap.xml || echo "absent from sitemap (correct)"
```

Expected: `index.html` present and only `index.html` — no `links.yml`,
`groups.yml`, `template.html` or `build.py`. One `const CATALOG`. Absent from
the sitemap.

- [ ] **Step 6: Commit**

```bash
git add docs/hooks.py tests/launch/test_hook.py
git commit -m "feat(launch): generate the page from an on_files hook

File.generated registers a virtual file, so docs_dir is never written
to. Writing there during a build makes mkdocs serve re-detect its own
write and rebuild roughly twice a second, indefinitely -- measured at 61
builds in 30 seconds on a minimal project.

Reloads the module when already imported, so an edit to build.py is
visible without restarting a long-running dev server.

Refs #4818"
```

---

### Task 9: The PR gate

**Files:**

- Create: `.github/workflows/pytest.yaml`

**Interfaces:**

- Consumes: `tests/launch/` from Tasks 2–8.
- Produces: a required-check candidate named `pytest / launch`.

Scoped to `tests/launch` only. `uv run pytest` on the whole tree dies at
collection — `tests/sensors/sftp/test_sensors_sftp_renlearn.py` does
`from tests.utils import ...` and there is no `pythonpath` config, taking 749
tests with it. That is pre-existing and out of scope.

- [ ] **Step 1: Create the workflow**

```yaml
name: pytest

on:
  pull_request:
    paths:
      - docs/launch/**
      - docs/hooks.py
      - tests/launch/**
      - mkdocs.yml
      - .github/workflows/pytest.yaml

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  launch:
    name: launch
    if: github.actor != 'dependabot[bot]'
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      # https://github.com/actions/checkout
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1

      # https://github.com/astral-sh/setup-uv
      - uses: astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9 # v9.0.0

      - name: Run the launch page tests
        run: uv run pytest tests/launch -v

      - name: Build the docs site
        run: uv run --group docs mkdocs build --site-dir site

      # https://github.com/actions/upload-artifact
      - name: Upload the rendered page for review
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2
        with:
          name: launch-page-preview
          path: site/launch/index.html
          # Below the publication threshold no page is generated. The
          # default (warn) would print a confusing warning on every PR.
          if-no-files-found: ignore
```

Pin `actions/upload-artifact` to whatever SHA the repo already uses if it
appears in another workflow; otherwise verify the SHA above resolves to v4.6.2
before committing.

- [ ] **Step 2: Verify the YAML parses and the steps match local behaviour**

```bash
cd /workspaces/teamster/.worktrees/launch-build-pipeline
uv run --with pyyaml --no-project python -c "
import yaml; yaml.safe_load(open('.github/workflows/pytest.yaml')); print('parses')"
uv run pytest tests/launch -v
uv run --group docs mkdocs build --site-dir /tmp/gate-check
test -f /tmp/gate-check/launch/index.html && echo "page present"
```

Expected: `parses`, all tests pass, `page present`.

- [ ] **Step 3: Lint everything changed on the branch**

```bash
cd /workspaces/teamster/.worktrees/launch-build-pipeline
git diff --name-only origin/main...HEAD | while read -r f; do
  test -f "$f" && printf '%s\n' "$f"
done | xargs ~/.cache/trunk/launcher/trunk check --force --no-fix </dev/null
```

Filter to existing paths first — a `--force` check hard-errors on a deleted
file, and this branch deletes `views.yml`.

- [ ] **Step 4: Commit and push**

```bash
git add .github/workflows/pytest.yaml
git commit -m "ci: add a pytest gate for the launch page

Runs tests/launch on any PR touching the catalog, the hook or the mkdocs
config, then builds the site and uploads the rendered page so a reviewer
can open it before approving.

Scoped to tests/launch: the full tree does not collect today.

Refs #4818"
git push -u origin anthonygwalters/feat/claude-launch-build-pipeline
```

- [ ] **Step 5: Open the PR**

Use `.github/pull_request_template.md`. Body must state:

- The move to `docs/launch/` and the four `exclude_docs` entries
- That `group` was folded in rather than deferred, and why (39 of 44 verified
  against a threshold of 25 means the page publishes on the next deploy)
- That the build is **not** wired into the deploy beyond what `docs/**` already
  covers
- The prerequisite: an admin must add `pytest / launch` to ruleset `816683`,
  which currently requires only dbt Cloud and Trunk, and
  `strict_required_status_checks_policy` is `false`

---

## Post-merge, not part of this plan

1. Ask an admin to add `pytest / launch` to ruleset `816683` and to enable
   `strict_required_status_checks_policy`. Until then the gate is advisory.
1. Decide the cutover threshold for retiring the Google Site. Distinct from
   `minimum_verified`, which only gates whether the page renders.
1. Verify the last 5 `needs-review` entries.
1. Source real URLs for the four dropped promo cards, or leave them out.
