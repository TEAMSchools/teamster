# PowerSchool Plugin Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the PowerSchool gradebook audit plugin, its build script, its
reference index, and both Claude skills into `teamster`, and make CI fail when
the plugin and the dbt models stop agreeing.

**Architecture:** Copy the `ps-plugins` working tree into a new top-level
`ps-plugins/` directory — a copy, not `git subtree`, because subtree would
import 5 licensed PDFs into a public history. Extend the existing
`scripts/build_plugin.py` with two contract checks rather than adding a second
validation pattern. Fold plugin maintenance into the existing `gradebook-audit`
skill, restructured into a router plus `references/` and `playbooks/`. Keep the
end-user skill a separate self-contained zip, built by CI.

**Tech Stack:** Python 3 standard library (the build script takes no
dependencies), pytest, GitHub Actions, dbt, markdown.

**Spec:**
[`docs/superpowers/specs/2026-09-21-ps-plugin-migration-design.md`](../specs/2026-09-21-ps-plugin-migration-design.md)

## Global Constraints

- **No PDF enters `teamster`.** Not the working tree, not history. `teamster` is
  public and the 5 PowerSchool reference PDFs are not redistributable.
- **`ps-plugins/gradebook-audit/WEB_ROOT/admin/gradebookaudit/` keeps every
  directory level.** `plugin.xml` and `permissions_root/*.xml` hard-code that
  path. Flattening it 404s the nav link and binds permissions to nothing, both
  silently. This level was lost once already.
- **`scripts/build_plugin.py` stays standard-library only.** It must run under a
  bare `python3` with no install step.
- **The end-user skill zip puts its files at the zip root**, not inside a
  `gradebook-expectations-upload/` folder. That is the layout that installs
  today.
- **The end-user skill is self-contained.** It reads the 2 Google Sheets and its
  own `references/`. It never references a `teamster` path, a dbt model, or the
  warehouse.
- **Plugin behaviour does not change in this plan.** The deployed v2.5 package
  and the dbt models are untouched except where a task says otherwise.
- **Every bare `#N` is an issue in `TEAMSchools/teamster`.**
- **Reference values, verified 2026-09-21:**
  - Plugin package: 8 files, 14,370 bytes, sha256
    `8cde2ff4b210f887fc3368f1c05df5c07e1f599aa2ccb17da0664762af2e0a78`
  - Skill zip: 9 files, 46,028 bytes
  - Named-query columns (9): `id`, `school_level`, `quarter`, `week_number`,
    `cnt_w`, `cnt_h`, `cnt_f`, `cnt_s`, `notes`
  - CSV header: `School Level,Quarter,Week Number,W,H,F,S,Notes`

## Out of scope

One of the spec's five open items is deliberately not a task here. An executor
who goes looking for it should stop.

- **Removing `ES` from the plugin.** Elementary keeps assignments in DeansList,
  so there is no PowerSchool gradebook to audit and the plugin should stop
  accepting `ES`. It needs a `plugin.xml` version bump and a deploy to 3
  instances, which this plan does not do. It rides the next plugin release.

## Review Focus

Five things the spec implies that no task's own deliverable would otherwise
exercise. Each has a test in the task that owns the code.

1. **A dbt model that adds a column the plugin does not declare must not fail
   the column check.** PowerSchool stamps `whocreated`, `whencreated`,
   `whomodified`, `whenmodified` onto every `U_` table and the named query does
   not list them. A naive set comparison fails on day one. Task 3.
2. **A plugin page with no CSV validator must not crash the header check.** The
   check parses a JavaScript array literal out of HTML; a page that does not
   contain one must produce a clear failure naming the file, not a `TypeError`.
   Task 4.
3. **The skill zip must not silently ship a broken relative link.** Every
   `playbooks/` and `references/` path named in `SKILL.md` must resolve inside
   the zip, or a T&L user hits a dead pointer with no error. Task 7.
4. **A second copy of the source sheet id must not creep back in.** Repointing
   one line in `sheets.md` does not stop the id appearing in a playbook. The
   check greps the whole skill folder. Task 6.
5. **`build_plugin.py` must still refuse a package with a missing page.** The
   existing structural validation is the reason the script exists; adding two
   checks must not regress it. Task 3.

---

### Task 1: Move the plugin tree into teamster

**Files:**

- Create: `ps-plugins/gradebook-audit/` (whole tree, copied)
- Create: `ps-plugins/scripts/build_plugin.py`
- Create: `ps-plugins/CLAUDE.md`, `ps-plugins/README.md`
- Modify: `.trunk/trunk.yaml`
- Modify: `.github/CODEOWNERS`
- Modify: `.github/workflows/claude-code-review.yaml`
- Create: `.github/workflows/build-plugin.yaml`

**Interfaces:**

- Consumes: the snapshot at `.claude/scratch/ps-plugins-snapshot/` (head
  `05e4f29`). `TEAMSchools/ps-plugins` is private again and the Codespace token
  cannot clone it; this snapshot is the only local copy.
- Produces: `ps-plugins/scripts/build_plugin.py`, which Tasks 3 and 4 extend,
  and `ps-plugins/gradebook-audit/`, whose paths every later task references.

- [ ] **Step 1: Copy the tree, excluding the PDFs and the discarded files**

```bash
w=/workspaces/teamster/.worktrees/GabyRangelB-feat-claude-ps-plugin-migration
s=/workspaces/teamster/.claude/scratch/ps-plugins-snapshot
mkdir -p "$w/ps-plugins"
cp -a "$s/gradebook-audit" "$w/ps-plugins/"
mkdir -p "$w/ps-plugins/scripts" "$w/ps-plugins/docs/reference"
cp -a "$s/scripts/build_plugin.py" "$w/ps-plugins/scripts/"
cp -a "$s/CLAUDE.md" "$s/README.md" "$w/ps-plugins/"
cp -a "$s/docs/reference/README.md" "$w/ps-plugins/docs/reference/"
cp -a "$s/.github/workflows/build-plugin.yaml" "$w/.github/workflows/"
rm -rf "$w/ps-plugins/gradebook-audit/dist"
```

- [ ] **Step 2: Prove no PDF came across**

```bash
find "$w/ps-plugins" -name '*.pdf' | wc -l
```

Expected: `0`. Any other number means stop and delete them before committing —
once a PDF is in a commit on this branch it is in the push.

- [ ] **Step 3: Verify the build reproduces the deployed package**

```bash
cd "$w/ps-plugins" && uv run --no-project python scripts/build_plugin.py gradebook-audit
unzip -v dist/gradebook_audit_v2.5.zip | tail -n +4 | head -8
```

Expected: `8 files, 14,370 bytes`, and per-file CRC32 values matching the spec's
Decision section. A differing CRC means the copy altered a file; re-copy rather
than editing.

- [ ] **Step 4: Stop prettier reformatting the PSHTML pages**

Add an entry to the **existing `lint.ignore:` list** in `.trunk/trunk.yaml`,
matching the key order its neighbours use. A top-level `ignore:` is not valid
config and trips `trunk/config-error`.

```yaml
lint:
  ignore:
    - paths:
        - ps-plugins/**/*.html
      linters:
        - prettier
```

PowerSchool PSHTML uses `~[...]` constructs that a generic HTML formatter
rewrites. `trunk-check.yaml` runs on every pull request, so without this the
first plugin PR silently mangles all 5 pages.

**`--force` deliberately bypasses this.** Trunk says so itself: a normal check
prints `Hint: use --force to check ignored files`. So the repo's
`trunk check --force` habit still reports prettier on these pages. That is
noise, not a regression — PR CI and the pre-push hook both run without `--force`
and honour the ignore. The danger is `trunk fmt --force`, which would rewrite
the pages rather than report them. Note that in `ps-plugins/CLAUDE.md` beside
the existing hand-zipping warning.

- [ ] **Step 5: Give the directory an owner and a reviewer**

Add to `.github/CODEOWNERS`, after the `/mcp/` line:

```text
/ps-plugins/ @TEAMSchools/admins @TEAMSchools/data-engineers
```

Add `ps-plugins/**` to the `paths:` list in
`.github/workflows/claude-code-review.yaml`. Without it, plugin pull requests
get no automated review — the filter is `src/**`, `tests/**`, `scripts/**`,
`.github/workflows/**`, none of which match a top-level `ps-plugins/`.

- [ ] **Step 6: Repoint the build workflow at the new paths**

In `.github/workflows/build-plugin.yaml`, replace both `paths:` lists (the
`push:` one and the `pull_request:` one — Actions does not support YAML anchors,
so they are duplicated by design) with:

```yaml
paths:
  - ps-plugins/**
  - src/dbt/powerschool/models/sis/staging/dlt/stg_powerschool__u_expectations.sql
  - tests/ps_plugins/**
  - .github/workflows/build-plugin.yaml
```

Change the build step's `run:` to `python3 ps-plugins/scripts/build_plugin.py`,
and the upload step's `path:` to `ps-plugins/dist/*.zip`.

`build_plugin.py` resolves `DIST` as `REPO / "dist"` where `REPO` is the
script's grandparent — now `ps-plugins/`, not the repository root. The artifact
path must follow it or the upload fails with `if-no-files-found: error`.

Keep the build step on `python3`, not `uv run`. The script is standard-library
only by design — that is why the upstream workflow ran `python3` and installed
nothing — and `ubuntu-latest` ships one. Using `uv` here would mean adding a
`setup-uv` step to run a script with no dependencies. Task 3 adds `setup-uv`
when it adds the pytest step, which genuinely needs it. The repo's "always
`uv run`" rule governs local work in the Codespace, where the venv matters; it
is not a CI rule.

The dbt path matters: Task 3's column check must fire when the **dbt** side
changes, not only when the plugin does. A one-sided change is exactly the
failure this plan exists to catch.

- [ ] **Step 7: Confirm no other workflow fires**

```bash
cd "$w" && grep -l 'ps-plugins' .github/workflows/*.yaml
```

Expected: only `build-plugin.yaml` and `claude-code-review.yaml`. The five
`deploy-prod-*`, `deploy-cube-mcp`, and `pytest` workflows filter on `src/**`,
`docs/launch/**`, and similar, so a top-level `ps-plugins/` matches none of
them. If one appears here, its filter is broader than expected — stop and
re-read it.

- [ ] **Step 8: Lint and commit**

```bash
git -C "$w" add ps-plugins .github .trunk
cd "$w" && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  $(git -C "$w" diff --name-only --cached) </dev/null
git -C "$w" commit -m "feat(ps-plugins): move the PowerSchool plugin into teamster"
```

Stage before checking — `--cached` reads the index, so checking first passes an
empty file list and reports a clean run over nothing.

---

### Task 2: Record the reference PDFs by Drive file ID

**Files:**

- Modify: `ps-plugins/docs/reference/README.md`

**Interfaces:**

- Consumes: `ps-plugins/docs/reference/README.md` from Task 1.
- Produces: nothing other tasks depend on.

- [ ] **Step 1: Replace each PDF's local filename with its Drive id**

The 5 PDFs already sit in the shared folder `1qjtKWlEE2XrfUXBh4QAodEX2g6c8do4T`
and match their repo copies byte for byte, so nothing is uploaded. Replace the
file list with:

```markdown
| Drive file ID                       | Document                           |
| ----------------------------------- | ---------------------------------- |
| `1LH0b5PSX_49PKnPOz3I2W_kD2QDI50Gd` | 2 - PS Plugins Intro               |
| `1jRvB4-Cc9N8kQ1zDOGb_bDNtOtDwrRl1` | 3 - PS Plugins XML                 |
| `1N8uHTD9oJhZpQAEa0UsYR2oy1yF6qC5r` | 4 - Database Extensions            |
| `18P1l28IanSON-lPuMCwR560HWKzxQujE` | 5 - Advanced User Guide            |
| `1ZxRjgezkF1Mi2ZTAyE6Q0WCwamq69mq5` | 6 - PowerTeacher Pro Customization |
| `1wtd7lmAB9LEI0yPtIQ6tTEdDjTJlt7TY` | 1 - PS Data Dictionary             |
```

Keep every existing sentence describing what each document covers and when to
consult it. Only the location changes.

- [ ] **Step 2: Say how to fetch one, both ways**

Add below the table:

```markdown
## Reading one

The folder is shared with the Codespaces service account
(`codespaces@teamster-332318.iam.gserviceaccount.com`), so a script under
`uv run` downloads the bytes to disk with Application Default Credentials. That
is the working path.

The Google Drive connector returns file content as base64, which
`check-output.sh` redacts as a high-entropy string, so binary files cannot be
read through the connector. Use it for metadata only.
```

A successor otherwise spends an afternoon rediscovering that the connector
cannot return a PDF.

- [ ] **Step 3: Lint and commit**

```bash
cd "$w" && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  ps-plugins/docs/reference/README.md </dev/null
git -C "$w" add -u
git -C "$w" commit -m "docs(ps-plugins): point the reference index at Drive"
```

---

### Task 3: Check the plugin's column set against the dbt model

**Files:**

- Modify: `ps-plugins/scripts/build_plugin.py`
- Create: `tests/ps_plugins/__init__.py` (empty)
- Test: `tests/ps_plugins/test_contract_checks.py`

**Interfaces:**

- Consumes: `ps-plugins/scripts/build_plugin.py` from Task 1.
- Produces: `named_query_columns(plugin_dir) -> set[str]`,
  `dbt_model_columns(sql_path) -> set[str]`, and
  `check_column_contract(plugin_dir, sql_path) -> list[str]` (a list of error
  strings, empty when the contract holds). Task 4 adds a sibling function and
  calls it from the same place.

- [ ] **Step 1: Write the failing tests**

Create `tests/ps_plugins/test_contract_checks.py`:

```python
"""Contract checks between the PowerSchool plugin and the dbt models."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "ps-plugins" / "gradebook-audit"
DBT_MODEL = (
    REPO
    / "src/dbt/powerschool/models/sis/staging/dlt/stg_powerschool__u_expectations.sql"
)

_spec = importlib.util.spec_from_file_location(
    "build_plugin", REPO / "ps-plugins" / "scripts" / "build_plugin.py"
)
build_plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_plugin)


def test_named_query_columns_are_the_nine_declared():
    assert build_plugin.named_query_columns(PLUGIN) == {
        "id",
        "school_level",
        "quarter",
        "week_number",
        "cnt_w",
        "cnt_h",
        "cnt_f",
        "cnt_s",
        "notes",
    }


def test_dbt_model_columns_include_the_powerschool_audit_quartet():
    columns = build_plugin.dbt_model_columns(DBT_MODEL)
    assert {"whocreated", "whencreated", "whomodified", "whenmodified"} <= columns
    assert "week_number" in columns


def test_column_contract_holds_today():
    assert build_plugin.check_column_contract(PLUGIN, DBT_MODEL) == []


def test_column_contract_fails_when_the_plugin_declares_an_unknown_column(tmp_path):
    queries = tmp_path / "queries_root"
    queries.mkdir()
    (queries / "q.xml").write_text(
        '<?xml version="1.0"?><queries><query coreTable="u_expectations">'
        "<columns><column column=\"u_expectations.made_up\">made_up</column>"
        "</columns></query></queries>"
    )
    errors = build_plugin.check_column_contract(tmp_path, DBT_MODEL)
    assert any("made_up" in e for e in errors)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/ps_plugins/test_contract_checks.py -v`

Expected: FAIL with
`AttributeError: module 'build_plugin' has no attribute 'named_query_columns'`.

- [ ] **Step 3: Implement the three functions**

Add to `ps-plugins/scripts/build_plugin.py`, above `def build(`:

```python
# PowerSchool stamps these onto every U_ table. The named query does not list
# them because the list page does not show them, so they are expected to appear
# on the dbt side and nowhere else. Without this exemption the contract check
# fails on its first run against a correct pair.
PS_AUDIT_COLUMNS = {"whocreated", "whencreated", "whomodified", "whenmodified"}

COLUMN_TAG = re.compile(r'<column\s+column="[^."]+\.([^"]+)"')


def named_query_columns(plugin_dir: Path) -> set[str]:
    """Every column the plugin's named queries declare on u_expectations."""
    columns: set[str] = set()
    for xml in sorted((plugin_dir / "queries_root").glob("*.xml")):
        columns |= set(COLUMN_TAG.findall(xml.read_text()))
    return columns


def dbt_model_columns(sql_path: Path) -> set[str]:
    """Column names the dbt staging model projects.

    The model enumerates its columns, so the names are readable without a dbt
    parse. Backticks around reserved words (`quarter`) are stripped.
    """
    body = sql_path.read_text()
    body = body[: body.index("from ")]
    columns: set[str] = set()
    for line in body.splitlines():
        line = line.strip().rstrip(",")
        if not line or line.startswith(("select", "--")):
            continue
        name = line.split(" as ")[-1] if " as " in line else line
        columns.add(name.strip().strip("`"))
    return columns


def check_column_contract(plugin_dir: Path, sql_path: Path) -> list[str]:
    """The plugin's declared columns must all exist in the dbt model."""
    declared = named_query_columns(plugin_dir)
    modelled = dbt_model_columns(sql_path)

    errors = [
        f"{c} is declared in a named query but the dbt model does not project it"
        for c in sorted(declared - modelled)
    ]
    errors += [
        f"{c} is in the dbt model but no named query declares it"
        for c in sorted(modelled - declared - PS_AUDIT_COLUMNS)
    ]
    return errors
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/ps_plugins/test_contract_checks.py -v`

Expected: 4 passed.

- [ ] **Step 5: Wire the check into the build and confirm it still refuses a
      broken package**

In `build()`, after the existing `errors = validate(staged, refs)` line:

```python
        errors += check_column_contract(plugin_dir, DBT_U_EXPECTATIONS)
```

and near `REPO`, add:

```python
# Resolved from the plugin directory so the script works from any cwd.
DBT_U_EXPECTATIONS = (
    REPO.parent
    / "src/dbt/powerschool/models/sis/staging/dlt/stg_powerschool__u_expectations.sql"
)
```

Then prove the pre-existing structural check still fires:

```bash
cd "$w" && mv ps-plugins/gradebook-audit/WEB_ROOT/admin/gradebookaudit/gradebook_expectations.html /tmp/gbe.html
uv run --no-project python ps-plugins/scripts/build_plugin.py gradebook-audit; echo "exit=$?"
mv /tmp/gbe.html ps-plugins/gradebook-audit/WEB_ROOT/admin/gradebookaudit/gradebook_expectations.html
```

Expected: `BUILD FAILED`, a line naming
`/admin/gradebookaudit/gradebook_expectations.html`, and `exit=1`.

- [ ] **Step 6: Prove the new check fails on a one-sided change**

```bash
cd "$w" && sed -i 's/cast(cnt_s as int) as cnt_s,/cast(cnt_s as int) as cnt_s,\n    1 as extra_col,/' \
  src/dbt/powerschool/models/sis/staging/dlt/stg_powerschool__u_expectations.sql
uv run --no-project python ps-plugins/scripts/build_plugin.py gradebook-audit; echo "exit=$?"
git -C "$w" checkout -- src/dbt/powerschool/models/sis/staging/dlt/stg_powerschool__u_expectations.sql
```

Expected: `BUILD FAILED`, a line reading
`extra_col is in the dbt model but no named query declares it`, and `exit=1`. Do
not claim this check works without running it — a check that cannot fail is
worse than none, because it reads as coverage.

- [ ] **Step 7: Add the pytest run to the workflow, then commit**

In `.github/workflows/build-plugin.yaml`, after the build step. The `setup-uv`
step is required — `ubuntu-latest` has no `uv`, and the build step deliberately
uses bare `python3` because the build script has no dependencies.

Copy the `setup-uv` line verbatim from `.github/workflows/pytest.yaml` — SHA,
version comment, and the URL comment above it. Do not paste a SHA from anywhere
else: `pinact` enforces pinned actions, dependabot moves this pin, and a stale
SHA copied from a plan is how two workflows drift onto different versions of the
same action.

```yaml
# https://github.com/astral-sh/setup-uv
- uses: astral-sh/setup-uv@<same SHA as pytest.yaml> # <same version comment>

- name: Run plugin contract tests
  run: uv run pytest tests/ps_plugins -v
```

```bash
git -C "$w" add ps-plugins tests/ps_plugins .github
git -C "$w" commit -m "feat(ps-plugins): fail the build when the plugin and dbt columns disagree"
```

---

### Task 4: Check the plugin's CSV header against the skill's documentation

**Files:**

- Modify: `ps-plugins/scripts/build_plugin.py`
- Test: `tests/ps_plugins/test_contract_checks.py`

**Interfaces:**

- Consumes: `check_column_contract` and the `build()` wiring from Task 3.
- Produces: `plugin_csv_header(plugin_dir) -> list[str]` and
  `check_csv_header_contract(plugin_dir, skill_dir) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/ps_plugins/test_contract_checks.py`:

```python
SKILL = REPO / "ps-plugins" / "skills" / "gradebook-expectations-upload"

EXPECTED_HEADER = [
    "school level",
    "quarter",
    "week number",
    "w",
    "h",
    "f",
    "s",
    "notes",
]


def test_plugin_csv_header_is_read_from_the_validator():
    assert build_plugin.plugin_csv_header(PLUGIN) == EXPECTED_HEADER


def test_missing_validator_reports_the_file_not_a_type_error(tmp_path):
    pages = tmp_path / "WEB_ROOT" / "admin" / "gradebookaudit"
    pages.mkdir(parents=True)
    (pages / "gradebook_expectations.html").write_text("<html>no validator</html>")
    with pytest.raises(ValueError, match="gradebook_expectations.html"):
        build_plugin.plugin_csv_header(tmp_path)
```

The second test is Review Focus item 2. A `TypeError` from unpacking `None`
tells a maintainer nothing; naming the file tells them where to look.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/ps_plugins/test_contract_checks.py -k csv -v`

Expected: FAIL with `AttributeError: ... has no attribute 'plugin_csv_header'`.

- [ ] **Step 3: Implement the two functions**

```python
# The import page validates an uploaded file against this literal. It is the
# authoritative header: a file that does not match is rejected outright with
# "Header row does not match template", and nothing imports.
CSV_EXPECTED = re.compile(r"var\s+expected\s*=\s*\[([^\]]+)\]")


def plugin_csv_header(plugin_dir: Path) -> list[str]:
    """The lower-cased column names the plugin's import validator accepts."""
    page = (
        plugin_dir
        / "WEB_ROOT/admin/gradebookaudit/gradebook_expectations.html"
    )
    match = CSV_EXPECTED.search(page.read_text())
    if match is None:
        raise ValueError(
            f"no `var expected = [...]` CSV validator found in {page.name}; "
            "the import page changed shape and this check needs updating"
        )
    return [v.strip().strip("'\"") for v in match.group(1).split(",")]


def check_csv_header_contract(plugin_dir: Path, skill_dir: Path) -> list[str]:
    """The end-user skill must document the header the plugin accepts."""
    documented = skill_dir / "references" / "csv-format.md"
    if not documented.is_file():
        return [f"{documented} is missing; the skill must document the header"]

    header = ",".join(plugin_csv_header(plugin_dir))
    text = documented.read_text().lower().replace(", ", ",")
    if header not in text:
        return [
            f"references/csv-format.md does not contain the header the plugin "
            f"accepts: {header}"
        ]
    return []
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/ps_plugins/test_contract_checks.py -k csv -v`

Expected: 2 passed.

- [ ] **Step 5: Wire it in, guarded until Task 6 lands the skill**

In `build()`, after the column-contract line:

```python
        if SKILL_DIR.is_dir():
            errors += check_csv_header_contract(plugin_dir, SKILL_DIR)
```

and beside `DBT_U_EXPECTATIONS`:

```python
SKILL_DIR = REPO / "skills" / "gradebook-expectations-upload"
```

The `is_dir()` guard keeps Tasks 3 and 4 independently mergeable. Task 6 removes
it once the skill exists.

- [ ] **Step 6: Commit**

```bash
git -C "$w" add ps-plugins tests/ps_plugins
git -C "$w" commit -m "feat(ps-plugins): fail the build when the CSV header and the skill disagree"
```

---

### Task 5: Fail a pull request that changes a plugin page without the skill

**Files:**

- Modify: `.github/workflows/build-plugin.yaml`

**Interfaces:**

- Consumes: the workflow from Task 1.
- Produces: nothing other tasks depend on.

- [ ] **Step 1: Add the drift gate**

`references/powerschool-navigation.md` describes screens the `WEB_ROOT` pages
render. No test can tell that prose describing a user interface has gone stale,
so this is a human gate with a machine trigger.

```yaml
- name: Check the walkthrough was considered
  if: github.event_name == 'pull_request'
  run: |
    base=$(git merge-base origin/${{ github.base_ref }} HEAD)
    pages=$(git diff --name-only "$base"...HEAD -- 'ps-plugins/gradebook-audit/WEB_ROOT/**' | wc -l)
    skill=$(git diff --name-only "$base"...HEAD -- 'ps-plugins/skills/**' | wc -l)
    if [ "$pages" -gt 0 ] && [ "$skill" -eq 0 ]; then
      echo "::error::This PR changes plugin pages but not the end-user skill."
      echo "Confirm references/powerschool-navigation.md still matches the"
      echo "screens, then rebuild the zip. If the walkthrough genuinely needs"
      echo "no change, add [skill-unaffected] to the PR title."
      exit 1
    fi
```

- [ ] **Step 2: Give the gate an escape hatch**

Some page changes genuinely do not touch a documented screen — a comment, a CSS
tweak. Before the `exit 1`, add:

```bash
          if echo "${{ github.event.pull_request.title }}" | grep -q '\[skill-unaffected\]'; then
            echo "Author asserted the walkthrough is unaffected."
            exit 0
          fi
```

A gate with no escape hatch gets disabled the first time it is wrong, and then
it protects nothing.

- [ ] **Step 3: Verify the checkout has enough history**

`actions/checkout` defaults to depth 1, which makes `git merge-base` fail. Add
to the checkout step:

```yaml
with:
  fetch-depth: 0
```

- [ ] **Step 4: Commit**

```bash
git -C "$w" add .github/workflows/build-plugin.yaml
git -C "$w" commit -m "ci(ps-plugins): gate plugin page changes on the walkthrough"
```

---

### Task 6: Seed the end-user skill, with its three fixes

**Files:**

- Create: `ps-plugins/skills/gradebook-expectations-upload/` (9 files, from the
  Desktop zip)
- Modify: `ps-plugins/scripts/build_plugin.py` (drop the Task 4 guard)
- Test: `tests/ps_plugins/test_skill_source.py`

**Interfaces:**

- Consumes: `.claude/scratch/skillzip-extracted/` (already unpacked, byte-
  identical to the installed copy) and `check_csv_header_contract` from Task 4.
- Produces: the skill folder Task 7 zips.

- [ ] **Step 1: Copy the 9 files in**

```bash
w=/workspaces/teamster/.worktrees/GabyRangelB-feat-claude-ps-plugin-migration
mkdir -p "$w/ps-plugins/skills/gradebook-expectations-upload"
cp -a /workspaces/teamster/.claude/scratch/skillzip-extracted/. \
  "$w/ps-plugins/skills/gradebook-expectations-upload/"
find "$w/ps-plugins/skills" -type f | wc -l
```

Expected: `9`.

- [ ] **Step 2: Write the failing tests for all three fixes**

Create `tests/ps_plugins/test_skill_source.py`:

```python
"""The end-user skill's three seeding-time corrections."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / "ps-plugins" / "skills" / "gradebook-expectations-upload"
SHEETS = SKILL / "references" / "sheets.md"

IMPORTRANGE_SOURCE_ID = "1ofCxW0pLniywn_XZT69S23vhcDs6y9ElAtJa5fTtiT0"
REPORTS_ID = "1Fx_tc1Bja2IWrIHyidTJrI4a0ZNcds07V29kjtkh3Go"


def test_skill_never_names_the_importrange_source_sheet():
    """Users get the Reports copy; the source is where refreshes are programmed."""
    offenders = [
        p.relative_to(SKILL)
        for p in SKILL.rglob("*.md")
        if IMPORTRANGE_SOURCE_ID in p.read_text()
    ]
    assert offenders == []


def test_sheets_reference_names_the_reports_copy():
    assert REPORTS_ID in SHEETS.read_text()


def test_sheets_reference_explains_the_two_drive_calls():
    text = SHEETS.read_text()
    for token in ("read_file_content", "get_file_metadata", "snippetVerbosity"):
        assert token in text, f"{token} missing; the dropped section was not restored"


def test_skill_uses_the_reports_tab_names():
    """The Reports copy is the user-friendly one; its tabs are named for people."""
    text = SHEETS.read_text()
    for tab in (
        "PS Full Calendar",
        "Plugin Data Raw",
        "Template QW-Date Crosswalk",
        "PS Plugin CSV Template",
    ):
        assert tab in text, f"{tab} is a tab on the Reports copy and is not named"


def test_rollover_no_longer_needs_an_existing_plugin_row():
    """PS Full Calendar carries week numbers, so the anchor problem is gone."""
    rollover = (SKILL / "playbooks" / "rollover.md").read_text()
    assert "PS Full Calendar" in rollover
    assert "🛑" not in (SKILL / "SKILL.md").read_text(), (
        "the open-gap note is answered; a stale warning teaches readers to "
        "distrust the live ones"
    )


def test_both_files_warn_about_the_academic_year_rollover():
    """The tab shows last year's weeks until the warehouse variable flips."""
    for name in ("playbooks/rollover.md", "references/sheets.md"):
        assert "academic_year" in (SKILL / name).read_text(), (
            f"{name} must tell the reader to confirm the academic_year column "
            "before trusting the calendar tab"
        )


def test_skill_never_uses_a_source_sheet_tab_name():
    """Those tabs exist only on the IMPORTRANGE Sources copy, which users never open."""
    offenders = []
    for p in SKILL.rglob("*.md"):
        body = p.read_text()
        for tab in ("ps_plugin_raw", "ps_plugin_data", "ps_all_weeks"):
            if tab in body:
                offenders.append(f"{p.relative_to(SKILL)}: {tab}")
    assert offenders == []
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/ps_plugins/test_skill_source.py -v`

Expected: all 7 FAIL. The seeded copy names the source sheet and its tab names,
lacks the Drive-call section, and does not know the full-calendar tab exists.

- [ ] **Step 4: Repoint the URL and remap every tab name**

In `references/sheets.md`, change the template sheet's URL from
`https://docs.google.com/spreadsheets/d/1ofCxW0pLniywn_XZT69S23vhcDs6y9ElAtJa5fTtiT0/edit`
to
`https://docs.google.com/spreadsheets/d/1Fx_tc1Bja2IWrIHyidTJrI4a0ZNcds07V29kjtkh3Go/edit`
and rename it from `rpt_gsheets__gradebook_audit_template` to **Gradebook Audit
Template**, which is what it is called in Drive.

**Then remap every tab name.** The Reports copy is the user-friendly one, so its
tabs carry user-friendly names — changing only the URL sends a reader to a sheet
whose tabs are not the ones the skill names. Verified 2026-09-22 by comparing
header rows; each pair below is identical in its columns.

The 3 presentation tabs pair one-to-one across the 2 sheets. Only
`PS Plugin CSV Template` has no counterpart — it is typed by hand, not fed by a
model.

| IMPORTRANGE Sources | Reports                      | Holds                                    |
| ------------------- | ---------------------------- | ---------------------------------------- |
| `ps_all_weeks`      | `PS Full Calendar`           | the full-year week grid (Step 6)         |
| `ps_plugin_raw`     | `Plugin Data Raw`            | what actually landed in `U_EXPECTATIONS` |
| `ps_plugin_data`    | `Template QW-Date Crosswalk` | the quarter-week to date mapping         |
| none                | `PS Plugin CSV Template`     | the literal CSV header row, to copy      |

The skill names only `ps_plugin_raw` and `ps_plugin_data` today, so those 2 are
renames and the other 2 are additions. Use the Reports column throughout — those
are the tabs a T&L reader sees.

`PS Plugin CSV Template` has no model behind it and no source-side twin. Its
header row is `School Level,Quarter,Week Number,W,H,F,S,Notes` — the same header
the plugin's validator enforces and `references/csv-format.md` documents, which
makes it a third place that header lives. Name it in `sheets.md` as the place to
copy the header from, so nobody retypes it by hand; a retyped header is rejected
outright by the import page.

Then grep the whole folder — a playbook may carry the old id or an old tab name:

```bash
cd "$w/ps-plugins/skills" && grep -rn "1ofCxW0\|ps_plugin_raw\|ps_plugin_data\|ps_all_weeks" . || echo "clean"
```

- [ ] **Step 5: Restore the dropped Drive-call section**

Copy the section at
`.claude/scratch/ps-plugins-snapshot/.claude/skills/gradebook-expectations-upload/SKILL.md`
lines 188 to 224 into `references/sheets.md`, under a
`## How to read these sheets` heading. It covers: which 2 Drive calls to make
and what each is good for; that the metadata read at `MAX_ALLOWED` silently
drops an empty `NOTE` column while the content read keeps columns aligned; never
identify a tab by its values; and stop when a read returns less than every tab's
rows and every tab's name.

Adjust only the sheet name to match Step 4. Do not rewrite the warnings — they
are the most operationally dangerous content in the file and were lost once
already.

- [ ] **Step 6: Document the all-weeks tab**

Add to `references/sheets.md`, in the list of tabs on the template sheet:

```markdown
**`PS Full Calendar`** — the whole school year's week grid, not just the weeks
already loaded into `U_EXPECTATIONS`. Use it to tell a week that has no
expectations apart from a week that does not exist; the other tabs cannot
distinguish those, because they only show rows PowerSchool already has. Columns
are `academic_year`, `region`, `school_level`, `quarter`, `week_number_quarter`,
`week_start_monday`, `week_end_friday`.
```

Name the tab, not the model behind it. A T&L reader is looking at tabs in a
spreadsheet; `rpt_gsheets__gradebook_audit_all_weeks` is a name they will never
see. The model belongs in the data-team skill, which Task 9 covers.

- [ ] **Step 6a: Rewrite the rollover week-numbering method**

This tab is what closes the skill's longest-standing gap, so the playbook has to
actually use it.

`playbooks/rollover.md` and `references/week-matching.md` derive a week number
by anchoring against a row that already exists in the plugin data. A genuine
rollover, run before the school year starts, has no such row — which is why the
Desktop skill carries a 🛑 saying the method is unsolved for that case and was
never exercised against a real start-of-year load.

`PS Full Calendar` removes the anchor entirely. It comes from
`int_students__calendar_week`, the PowerSchool calendar, not from
`U_EXPECTATIONS`, and it already carries `week_number_quarter` beside
`week_start_monday` and `week_end_friday`. Reading a week number off it needs no
expectations row to exist.

Rewrite both files so the method is: find the row in `PS Full Calendar` whose
`week_start_monday` and `week_end_friday` bracket the dates on the Academics
tab, and take its `week_number_quarter`. Delete the 🛑 open-gap note from
`SKILL.md`'s maintainer section — it is answered, and a stale warning about a
solved problem teaches a reader to distrust the warnings that are still live.

State the precondition plainly, because it has 2 parts and the second one is a
trap:

1. The school year's calendar is loaded in PowerSchool.
2. **`current_academic_year` has been rolled over in the warehouse.**

The tab filters `academic_year = {{ var("current_academic_year") }}`. A
PowerSchool instance can be sitting in the next school year all summer while the
warehouse variable still points at the old one, and until someone rolls that
variable over, `PS Full Calendar` shows **last year's** weeks.

That is worse than showing nothing. Last year's week numbers and dates look
entirely plausible — same columns, same shape, same quarter names — so a
rollover run in that window produces a confident, wrong upload with no error
anywhere. Write the check as an instruction the reader cannot skip: **before
using this tab for a rollover, confirm the `academic_year` column shows the year
you are loading.** One glance at the column answers it.

Put the same warning in `references/sheets.md` beside the tab description. A
reader who reaches the tab from the troubleshooting playbook never opens
`rollover.md`.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/ps_plugins/test_skill_source.py -v`

Expected: 7 passed.

- [ ] **Step 8: Drop the Task 4 guard and confirm the header check runs**

In `ps-plugins/scripts/build_plugin.py`, replace:

```python
        if SKILL_DIR.is_dir():
            errors += check_csv_header_contract(plugin_dir, SKILL_DIR)
```

with:

```python
        errors += check_csv_header_contract(plugin_dir, SKILL_DIR)
```

Then prove the header check now fails on a one-sided change:

```bash
cd "$w" && sed -i 's/School Level,Quarter,Week Number,W,H,F,S,Notes/School Level,Quarter,Week,W,H,F,S,Notes/' \
  ps-plugins/skills/gradebook-expectations-upload/references/csv-format.md
uv run --no-project python ps-plugins/scripts/build_plugin.py gradebook-audit; echo "exit=$?"
git -C "$w" checkout -- ps-plugins/skills/gradebook-expectations-upload/references/csv-format.md
```

Expected: `BUILD FAILED`, a line naming the header, and `exit=1`.

- [ ] **Step 9: Commit**

```bash
git -C "$w" add ps-plugins tests/ps_plugins
git -C "$w" commit -m "feat(ps-plugins): seed the end-user skill and fix its three defects"
```

---

### Task 7: Build the skill zip and attach it to a release

**Files:**

- Create: `ps-plugins/scripts/build_skill.py`
- Modify: `ps-plugins/skills/gradebook-expectations-upload/SKILL.md`
- Modify: `.github/workflows/build-plugin.yaml`
- Test: `tests/ps_plugins/test_build_skill.py`

**Interfaces:**

- Consumes: the skill folder from Task 6.
- Produces: `dist/gradebook_expectations_upload_v<version>.zip`, whose files sit
  at the zip root.

- [ ] **Step 1: Stamp a version into the skill**

Add to the YAML frontmatter of
`ps-plugins/skills/gradebook-expectations-upload/SKILL.md`, after `name:`:

```yaml
version: "1.0.0"
```

The version is how a support conversation resolves "the screen does not match
the instructions" — it says which build the person is running. It matters most
on the per-user install path, which does not auto-update.

- [ ] **Step 2: Write the failing tests**

Create `tests/ps_plugins/test_build_skill.py`:

```python
"""The end-user skill zip: layout, completeness, and link integrity."""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / "ps-plugins" / "skills" / "gradebook-expectations-upload"

_spec = importlib.util.spec_from_file_location(
    "build_skill", REPO / "ps-plugins" / "scripts" / "build_skill.py"
)
build_skill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_skill)


def test_version_is_read_from_the_frontmatter():
    assert build_skill.skill_version(SKILL) == "1.0.0"


def test_zip_puts_files_at_the_root(tmp_path):
    out = build_skill.build(SKILL, tmp_path)
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
    assert "SKILL.md" in names, "SKILL.md must be at the zip root, not nested"
    assert not any(n.startswith("gradebook-expectations-upload/") for n in names)


def test_zip_carries_all_nine_files(tmp_path):
    out = build_skill.build(SKILL, tmp_path)
    with zipfile.ZipFile(out) as z:
        assert len([n for n in z.namelist() if not n.endswith("/")]) == 9


def test_every_relative_link_in_the_skill_resolves(tmp_path):
    """A dead pointer in the zip is silent for the user who hits it."""
    out = build_skill.build(SKILL, tmp_path)
    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
    missing = build_skill.unresolved_links(SKILL)
    assert missing == [], f"broken relative links: {missing}"
    assert "references/sheets.md" in names
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/ps_plugins/test_build_skill.py -v`

Expected: FAIL — `build_skill.py` does not exist.

- [ ] **Step 4: Write the build script**

Create `ps-plugins/scripts/build_skill.py`:

```python
#!/usr/bin/env python3
"""Package the end-user Claude skill into an installable zip.

The files go at the ZIP ROOT, not inside a folder. That is the layout that
installs correctly in Claude Desktop today; nesting them breaks the install with
no useful error.

Standard library only, like build_plugin.py.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "gradebook-expectations-upload"
DIST = REPO / "dist"  # ps-plugins/dist, beside the plugin zips

VERSION = re.compile(r'^version:\s*"([^"]+)"', re.MULTILINE)
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def skill_version(skill_dir: Path) -> str:
    match = VERSION.search((skill_dir / "SKILL.md").read_text())
    if match is None:
        raise ValueError("SKILL.md frontmatter has no version: field")
    return match.group(1)


def unresolved_links(skill_dir: Path) -> list[str]:
    """Relative markdown links that do not resolve inside the skill folder."""
    missing: list[str] = []
    for md in sorted(skill_dir.rglob("*.md")):
        for target in MD_LINK.findall(md.read_text()):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            if not (md.parent / target.split("#")[0]).exists():
                missing.append(f"{md.relative_to(skill_dir)} -> {target}")
    return missing


def build(skill_dir: Path, dist: Path) -> Path:
    broken = unresolved_links(skill_dir)
    if broken:
        raise ValueError(f"broken relative links: {broken}")

    dist.mkdir(parents=True, exist_ok=True)
    out = dist / f"gradebook_expectations_upload_v{skill_version(skill_dir)}.zip"
    if out.exists():
        out.unlink()

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(skill_dir.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(skill_dir))
    return out


def main() -> int:
    out = build(SKILL, DIST)
    with zipfile.ZipFile(out) as z:
        count = len([n for n in z.namelist() if not n.endswith("/")])
    print(f"wrote {out.name} ({count} files, {out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/ps_plugins/test_build_skill.py -v`

Expected: 4 passed.

- [ ] **Step 6: Prove the link check catches a dead pointer**

```bash
cd "$w" && sed -i 's|playbooks/rollover.md|playbooks/does-not-exist.md|' \
  ps-plugins/skills/gradebook-expectations-upload/SKILL.md
uv run --no-project python ps-plugins/scripts/build_skill.py; echo "exit=$?"
git -C "$w" checkout -- ps-plugins/skills/gradebook-expectations-upload/SKILL.md
```

Expected: a `ValueError` naming `playbooks/does-not-exist.md`, and a non-zero
exit.

- [ ] **Step 7: Build and attach the zip in CI**

Add to `.github/workflows/build-plugin.yaml`, after the plugin build step:

```yaml
- name: Build the end-user skill zip
  run: uv run --no-project python ps-plugins/scripts/build_skill.py

- name: Upload the skill zip
  uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
  with:
    name: gradebook-expectations-upload
    path: ps-plugins/dist/gradebook_expectations_upload_*.zip
    if-no-files-found: error
```

Publishing a GitHub release needs `contents: write`, which this workflow
deliberately does not hold — the artifact is the download, and an admin takes it
from the workflow run. Widening the token to publish releases is a separate
decision, not a step here.

- [ ] **Step 8: Commit**

```bash
git -C "$w" add ps-plugins tests/ps_plugins .github
git -C "$w" commit -m "feat(ps-plugins): build the end-user skill zip in CI"
```

---

### Task 8: Restructure the gradebook-audit skill into a router

**Files:**

- Modify: `.claude/skills/gradebook-audit/SKILL.md`
- Create: `.claude/skills/gradebook-audit/references/*.md`
- Create: `.claude/skills/gradebook-audit/playbooks/*.md`

**Interfaces:**

- Consumes: the current 682-line `SKILL.md` (649 on `main`, plus #5328's
  rollover changes already on this branch).
- Produces: the router that Task 9 adds two responsibilities to.

- [ ] **Step 1: Read the model this repo already has**

Read `.claude/skills/tableau-workbook-xml/SKILL.md` — 263 lines routing to 7
files under `references/`. It is the shape to copy. Note that it names what each
reference covers and when to read it, and holds no procedure itself.

Use `references/` (not `reference/`): 2 of the 3 existing multi-file skills use
the plural, and so does the end-user skill.

- [ ] **Step 2: Split the content, moving text rather than rewriting it**

Move whole sections out of `SKILL.md` into:

- `references/data-model.md` — lineage, flag definitions, scaffold structure
- `references/summer-toggle.md` — the rollover toggle points, all 6
- `playbooks/change-a-flag.md` — the add/remove/edit flag procedure
- `playbooks/add-a-region.md`
- `playbooks/academic-year-rollover.md`

Move the text verbatim. A restructure that also rewrites cannot be reviewed for
loss, and the Desktop skill's restructure lost its most dangerous section
exactly this way.

- [ ] **Step 3: Prove nothing was lost**

```bash
cd "$w/.claude/skills/gradebook-audit"
git -C "$w" show HEAD:.claude/skills/gradebook-audit/SKILL.md \
  | grep -oE '[a-z_]{4,}' | sort -u > /tmp/before.txt
cat SKILL.md references/*.md playbooks/*.md \
  | grep -oE '[a-z_]{4,}' | sort -u > /tmp/after.txt
comm -23 /tmp/before.txt /tmp/after.txt
```

Expected: empty, or only words whose loss you can explain out loud. Any model
name, column name, or procedure keyword appearing here is content that vanished.

- [ ] **Step 4: Write the router**

`SKILL.md` keeps its frontmatter, the "Always read first" pointer to
`docs/models/gradebook-audit-data-model.md`, the `academic_year` gotcha, and a
routing table of one row per playbook and reference. Target under 150 lines. It
holds no procedure.

- [ ] **Step 5: Walk it cold**

Open `SKILL.md` as if you had never seen this domain. Pick a task — "a flag is
not firing". Can you reach the right file from the entry file plus at most 2
more reads? If not, the routing table is wrong; fix it before committing.

- [ ] **Step 6: Lint and commit**

```bash
cd "$w" && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  .claude/skills/gradebook-audit/SKILL.md \
  .claude/skills/gradebook-audit/references/*.md \
  .claude/skills/gradebook-audit/playbooks/*.md </dev/null
git -C "$w" add .claude/skills/gradebook-audit
git -C "$w" commit -m "refactor(gradebook-audit): split the skill into a router and shelves"
```

---

### Task 9: Give the skill its two new responsibilities

**Files:**

- Create: `.claude/skills/gradebook-audit/playbooks/maintain-the-plugin.md`
- Create: `.claude/skills/gradebook-audit/playbooks/ship-a-skill-update.md`
- Create: `.claude/skills/gradebook-audit/references/published-sheets.md`
- Modify: `.claude/skills/gradebook-audit/SKILL.md`

**Interfaces:**

- Consumes: the router from Task 8; the build scripts from Tasks 3, 4 and 7.
- Produces: the skill's final shape.

- [ ] **Step 1: Write the plugin maintenance playbook**

`playbooks/maintain-the-plugin.md` covers: where the source lives
(`ps-plugins/gradebook-audit/`); bump `version` in `plugin.xml` on every change;
build with `uv run --no-project python ps-plugins/scripts/build_plugin.py`,
never by hand; the `gradebookaudit/` folder level is load-bearing; the table
must exist in PowerSchool before the plugin enables, or it 500s; deploy to
Newark, Camden, Paterson and the test instance individually, and update the
deployment tracker in `ps-plugins/README.md`; reference PDFs are in Drive,
indexed at `ps-plugins/docs/reference/README.md`.

Point at `ps-plugins/CLAUDE.md` for the PS gotchas rather than restating them.

- [ ] **Step 2: Write the propagation playbook**

`playbooks/ship-a-skill-update.md`. Open it with the instruction that makes it
work:

```markdown
Write for a Teaching & Learning reader, not a data-team one. No dbt model names,
no SQL, no BigQuery. Describe what changes on screen and what they should do
differently. If a sentence only makes sense to someone who has read the plugin
source, rewrite it.
```

Then the sequence: change the skill source under
`ps-plugins/skills/gradebook-expectations-upload/`; bump `version` in its
frontmatter; let CI build the zip; download it from the workflow run; then
branch — **organization skills** (an admin uploads at claude.ai under
Organization settings, Skills, Add; every user gets it automatically; needs a
Team or Enterprise plan and code execution enabled) or **per-user install**
(send the zip, each person installs it, `INSTALL.md` covers it, no auto-update
so the version stamp is the only way to tell who is behind).

Both branches are written out. The one that is unavailable is the one somebody
will need.

- [ ] **Step 3: Write the published-sheets reference**

`references/published-sheets.md`: the sheets come in pairs — the Connected
Sheets extraction in IMPORTRANGE Sources named after the model, and the
friendly-named copy in Reports that users open. **A change to either goes in
both.** Point at `docs/guides/google-sheets.md` for the per-change table rather
than duplicating it; name the 4 models on the upload-template exposure and which
tab each feeds.

- [ ] **Step 4: Add the three rows to the router**

Add one row per new file to `SKILL.md`'s routing table, and extend the skill's
stated scope from 1 responsibility to 4: the dbt models and dashboard, the
PowerSchool plugin, propagating a change to the end-user skill, and the
published sheet pairs.

- [ ] **Step 5: Walk it cold again**

Pick "the plugin screen changed and T&L needs to know". Entry file plus at most
2 reads should land you in `ship-a-skill-update.md` with the plain-language
instruction in view.

- [ ] **Step 6: Lint and commit**

```bash
cd "$w" && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  .claude/skills/gradebook-audit/SKILL.md \
  .claude/skills/gradebook-audit/references/*.md \
  .claude/skills/gradebook-audit/playbooks/*.md </dev/null
git -C "$w" add .claude/skills/gradebook-audit
git -C "$w" commit -m "feat(gradebook-audit): own the plugin, the skill handoff, and the sheet pairs"
```

---

### Task 10: Open the pull request and retire the source repository

**Files:**

- None in this repository beyond the PR body.

**Interfaces:**

- Consumes: everything above.

- [ ] **Step 1: Run the full check locally before pushing**

```bash
cd "$w" && uv run pytest tests/ps_plugins -v
uv run --no-project python ps-plugins/scripts/build_plugin.py
uv run --no-project python ps-plugins/scripts/build_skill.py
```

Expected: all tests pass; the plugin zip is 8 files at 14,370 bytes; the skill
zip is 9 files with `SKILL.md` at the root.

- [ ] **Step 2: Confirm no PDF is anywhere in the branch's history**

```bash
git -C "$w" log --all --diff-filter=A --name-only --pretty=format: \
  origin/main..HEAD | grep -i '\.pdf$' | sort -u
```

Expected: empty. This is the one failure that cannot be undone after a push.

- [ ] **Step 3: Open the pull request**

Body from `.github/pull_request_template.md`, plain language per
`.github/PLAIN_LANGUAGE.md`. Reference `Closes #5433`. Mention that #5328 was
closed and ported here, and that #5440 tracks the org-skills API gap.

- [ ] **Step 4: Watch CI**

dbt Cloud CI now runs on this branch — it stopped being docs-only when #5328's
models landed. `claude-review` fires too. Invoke `pr-ci-review` for the check
surfaces and `superpowers:receiving-code-review` before acting on findings.

- [ ] **Step 5: Retire the source repository, after merge**

Replace `TEAMSchools/ps-plugins`'s `README.md` with a pointer to `teamster` and
to the spec, **then** archive it. Archiving makes the repo read-only, so the
README edit has to come first or it needs unarchiving.

Keep it private. Its history holds the 5 PDFs, which is the reason this
migration copied the tree instead of importing it.
