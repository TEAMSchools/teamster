# Dashboard Build Plans in Asana Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each dashboard task in "Data Marts + Semantic Layer" holds its dated
PR plan, with its measure and dimension rows under the PRs that ship them, and
the build status page keeps reading every row through the move.

**Architecture:** First the 2 readers learn the new shape: the sync script
(`scripts/asana_sync.py`, ported from an unmerged branch and refactored into
testable functions, then scheduled) and the status-page generator (another
repo). Then the cube-builder skill writes the shape. Then Literacy, and STAT
after it, move their rows, with page counts compared before and after.

**Tech Stack:** Python 3 standalone scripts (`requests` for the sync script,
stdlib for the generator), pytest, GitHub Actions, the Asana REST API and the
Asana MCP, Markdown skill files.

**Spec:**
`docs/superpowers/specs/2026-11-23-asana-dashboard-build-plans-design.md`

## Global Constraints

- Project: "Data Marts + Semantic Layer", gid `1213735218595734`.
- Row tags: `measure`, `dimension`. Status tags: `needs-data`, `needs-cube`. A
  done row carries no status tag.
- PR type lives in the PR task's name: `(dbt)` or `(Cube)`.
- Confirm item name: `Confirm <build> shipped with <dashboard>`.
- Holder task names: `Already in Cube`, `Deferred`.
- A row is done when every Cube member its notes name is on a public view on
  `main`.
- The sync script runs every 4 hours, just before the generator (generator cron
  `0 */4 * * *`), with an Asana token stored as a GitHub secret.
- Asana caps a task at 30 dependencies plus dependents: never link rows to the
  Validate task.
- Asana text carries field names, member names and counts only, never a
  student's or staff member's name, number or row.
- Rows do not move off table tasks until Tasks 1 to 4 have shipped.

## Review Focus

- A row moved under a PR task without a `measure` or `dimension` tag drops off
  the page silently. The sync script must report it (Task 2 test
  `test_untagged_row_under_dashboard_is_reported`).
- A synced `#NNNN | feat(dbt,cube): ...` task has no `(dbt)` / `(Cube)`. Its
  type must come from the conventional-commit scope, and `dbt` wins when both
  appear (Task 2 test `test_pr_type_from_synced_name`).
- The scheduled run has no `~/asana-sync/validation/latest.json`. It must leave
  every `validated` tag alone, not strip them (Task 1 test
  `test_missing_validation_file_means_no_verdicts`).
- A row under its own dashboard's PR whose `Used by:` also names that dashboard
  must count once, not twice (Task 4 test
  `test_row_under_own_dashboard_counts_once`).
- A merged parent PR whose members are not on `main` yet must read `needs-cube`,
  not done and not `needs-data` (Task 2 test
  `test_merged_parent_not_live_is_needs_cube`).

---

### Task 1: Port the sync script and make it testable

Behavior stays as it is on the branch, except the 2 fixes below. Rows still come
from dashboard subtasks and table tasks.

**Files:**

- Create: `scripts/asana_sync.py` (start from
  `git show origin/cristinabaldor/feat/claude-asana-sync-done-when-live:scripts/asana_sync.py`;
  port this 1 file, not the branch: the branch also carries a retired
  `cube_validate` package)
- Test: `tests/scripts/test_asana_sync.py`
- Modify: `scripts/CLAUDE.md` (1 catalog row)

**Interfaces:**

- Produces:
  - `main(argv: list[str]) -> int`. Every network call and `sys.exit` moves
    inside it; importing the module does nothing.
  - `load_validation(path: str) -> dict | None`: `None` when the file is
    missing.
  - `dashboard_gids(tasks: list[dict]) -> list[str]`: gids of top-level tasks
    tagged `dashboard`. Replaces the fixed `DASHBOARDS` list.
  - `row_kind(task: dict) -> str | None`: `"measure"`, `"dimension"` or `None`,
    from its tags.
  - `want_status(*, live: bool, stage_blockers: list[dict], needs_line: str | None) -> str | None`:
    today's rule, unchanged (an open `mart` or `addition` blocker means
    `needs-data`, any other open blocker means `needs-cube`, then the `Needs:`
    line).
- The module keeps a PEP 723 header with `requests`.

- [ ] **Step 1: Write the failing tests**

```python
def test_import_has_no_side_effects(): ...  # loading the module makes no request and does not exit
def test_missing_validation_file_means_no_verdicts(tmp_path):
    assert mod.load_validation(str(tmp_path / "latest.json")) is None
def test_dashboard_gids_reads_the_tag():
    tasks = [{"gid": "1", "tags": [{"name": "dashboard"}]}, {"gid": "2", "tags": []}]
    assert mod.dashboard_gids(tasks) == ["1"]
def test_want_status_table_rules():
    mart = {"kind": "mart", "completed": False}
    view = {"kind": "view", "completed": False}
    assert mod.want_status(live=False, stage_blockers=[mart, view], needs_line=None) == "needs-data"
    assert mod.want_status(live=False, stage_blockers=[view], needs_line=None) == "needs-cube"
    assert mod.want_status(live=False, stage_blockers=[], needs_line="data") == "needs-data"
    assert mod.want_status(live=True, stage_blockers=[mart], needs_line=None) is None
```

Load the module with `importlib.util.spec_from_file_location`, per
`scripts/CLAUDE.md` _Testing standalone PEP 723 scripts_.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run --with requests pytest tests/scripts/test_asana_sync.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Port and refactor `scripts/asana_sync.py`**

`main` skips step 5 (the `validated` tags) entirely when `load_validation`
returns `None`, and prints that it did. Keep `--apply` and `--only`; `--only`
now checks the gid against `dashboard_gids`.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run --with requests pytest tests/scripts/test_asana_sync.py -v`
Expected: PASS.

- [ ] **Step 5: Preview against live Asana (user's terminal: needs their
      ASANA_PAT)**

Run:
`uv run --with requests python scripts/asana_sync.py --only 1213823922716082`
Expected: the same planned changes the branch version prints for Literacy, plus
"no validation file: validated tags left alone" when the file is absent.

- [ ] **Step 6: Commit**

```bash
git add scripts/asana_sync.py tests/scripts/test_asana_sync.py scripts/CLAUDE.md
git commit -m "feat(scripts): port the Asana sync script with testable functions"
```

### Task 2: Teach the sync script the new shape

**Files:**

- Modify: `scripts/asana_sync.py`
- Test: `tests/scripts/test_asana_sync.py`

**Interfaces:**

- Consumes: `row_kind`, `want_status`, `dashboard_gids` from Task 1.
- Produces:
  - `pr_type(name: str) -> str | None`: `"dbt"` or `"cube"`. Reads `(dbt)` /
    `(Cube)`; for a synced `#NNNN | <type>(<scope>): ...` name, reads the scope,
    and `dbt` wins when both appear.
  - `rows_under(dashboard: dict, children: list[dict], grandchildren: dict[str, list[dict]]) -> tuple[list[tuple[dict, dict | None]], list[dict]]`:
    rows tagged `measure` or `dimension` directly under the dashboard (parent
    `None`) or under any of its subtasks (parent = that subtask), plus the
    untagged grandchildren under a PR task, which are reported, not synced.
    Holders (`Already in Cube`, `Deferred`) count as parents with no type.
  - `want_status_pr(*, live: bool, parent: dict, parent_blockers: list[dict]) -> str | None`:
    `None` when live; `needs-data` when the parent is an open `dbt` PR or any
    open `dbt` PR blocks the parent; otherwise `needs-cube`. Holders give
    `None`.

- [ ] **Step 1: Write the failing tests**

```python
def test_pr_type_from_bracket():
    assert mod.pr_type("PR SW1 (dbt): fct_sight_words") == "dbt"
    assert mod.pr_type("PR SW2 (Cube): sight_words cube and sight_words_view") == "cube"
def test_pr_type_from_synced_name():
    assert mod.pr_type("#6461 | feat(cube): build Literacy Dashboard in Cube") == "cube"
    assert mod.pr_type("#6394 | feat(dbt,cube): make assessment tagging checks possible") == "dbt"
    assert mod.pr_type("Validate Literacy Dashboard in Cube") is None
def test_rows_under_finds_both_depths(): ...  # direct measure row (parent None) and a dimension row under a PR (parent = PR)
def test_untagged_row_under_dashboard_is_reported(): ...  # untagged grandchild of a PR task lands in the report list
def test_open_dbt_blocker_is_needs_data():
    parent = {"name": "PR PM4 (Cube): PM cubes", "completed": False}
    dbt = {"name": "PR PM1 to PM3 (dbt): DIBELS PM facts", "completed": False}
    assert mod.want_status_pr(live=False, parent=parent, parent_blockers=[dbt]) == "needs-data"
    assert mod.want_status_pr(live=False, parent=parent, parent_blockers=[]) == "needs-cube"
def test_merged_parent_not_live_is_needs_cube():
    parent = {"name": "PR L1 (Cube): national_percentile", "completed": True}
    assert mod.want_status_pr(live=False, parent=parent, parent_blockers=[]) == "needs-cube"
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run --with requests pytest tests/scripts/test_asana_sync.py -v`
Expected: the 6 new tests FAIL.

- [ ] **Step 3: Implement in `scripts/asana_sync.py`**

`main` fetches each dashboard's subtasks and their subtasks, syncs rows from
`rows_under` with `want_status_pr` when the parent is a PR task and
`want_status` when the row still has stage blockers, and prints the untagged
rows under a "Rows with no kind tag" heading. Table-task rows keep today's path
until no table task has rows.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run --with requests pytest tests/scripts/test_asana_sync.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/asana_sync.py tests/scripts/test_asana_sync.py
git commit -m "feat(scripts): sync rows under PR tasks and holders"
```

### Task 3: Schedule the sync script

**Files:**

- Create: `.github/workflows/asana-sync.yaml`

- [ ] **Step 1: Write the workflow**

Triggers: `schedule: cron: '40 3-23/4 * * *'` (20 minutes before each generator
run) and `workflow_dispatch` with a boolean input `apply` (default `true` on
schedule, chosen on dispatch). Job gate `github.actor != 'dependabot[bot]'`.
Steps: `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1` with
`fetch-depth: 0` (the script reads `origin/main`),
`astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2 # v10.3.3`, then
`uv run --with requests python scripts/asana_sync.py` plus `--apply` when
`apply` is true, with `ASANA_PAT: ${{ secrets.ASANA_PAT }}`. Permissions:
`contents: read`.

- [ ] **Step 2: Lint it**

Run (cwd in the worktree):
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .github/workflows/asana-sync.yaml </dev/null`
Expected: no actionlint or yamllint findings.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/asana-sync.yaml
git commit -m "ci: run the Asana sync every 4 hours before the status page refresh"
```

- [ ] **Step 4: Hand the secret to the user**

The user adds the repository secret `ASANA_PAT` (their token) in the repo
settings; it needs their admin rights. After merge, dispatch the workflow once
with `apply: false` and read the preview in the run log.

### Task 4: Teach the generator the new shape (repo `cristinabaldor/semantic-layer-dashboard`)

**Files:**

- Modify: `generate_dashboard.py` (in a clone under the session scratchpad)
- Create: `tests/test_generate_dashboard.py` in that repo

**Interfaces:**

- Produces: `linked_rows(tasks)` also returns rows tagged `measure` or
  `dimension` that sit under any subtask of a `dashboard` task, counted for that
  dashboard and for each dashboard their `Used by:` links. `fetch_project`
  fetches the subtasks of each dashboard subtask that has subtasks.

- [ ] **Step 1: Capture the baseline**

Run the current generator (user's terminal or `workflow_dispatch`), then save
per-dashboard counts:
`jq '[.dashboards[] | {name, m: (.measures|length), d: (.dimensions|length)}]'`
over the object in `data.js`, to `<scratchpad>/page-baseline.json`.

- [ ] **Step 2: Write the failing tests**

```python
def test_row_under_pr_task_counts_for_its_dashboard(): ...  # measure row under a PR subtask of dashboard D appears in D's measures
def test_dimension_row_under_pr_needs_its_tag(): ...  # untagged grandchild is not a row
def test_row_under_own_dashboard_counts_once(): ...  # Used by: names D too; D lists it once
def test_table_rows_still_read(): ...  # a table task's rows keep counting while tables remain
```

- [ ] **Step 3: Run them to see them fail**

Run: `uv run --with pytest pytest tests/test_generate_dashboard.py -v` Expected:
the first 3 FAIL, the table test PASSES.

- [ ] **Step 4: Implement in `generate_dashboard.py`**

Keep the docstring's _What it reads_ section true to the new behavior.

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run --with pytest pytest tests/test_generate_dashboard.py -v` Expected:
PASS.

- [ ] **Step 6: Compare with the baseline**

Run the new generator and the same `jq`. Expected: identical counts for every
dashboard, since no row has moved yet. Literacy's untagged plan subtasks add
nothing.

- [ ] **Step 7: Commit and push to that repo's `main`** (its push trigger reruns
      the Action)

```bash
git add generate_dashboard.py tests/test_generate_dashboard.py
git commit -m "feat: read measure and dimension rows under a dashboard's PR tasks"
```

### Task 5: Make the cube-builder skill write the shape

**Files:**

- Modify: `.claude/skills/cube-builder/SKILL.md` (_Rules_, _Plan_ step 3,
  _Build_, _Finish_)

- [ ] **Step 1: Find every restatement**

Run:
`rg -n -i 'only for a miss|blocked-by list|Asana' .claude docs/guides CLAUDE.md`
Each hit that restates a rule this task changes gets updated in the same commit.

- [ ] **Step 2: Edit the skill**

- _Rules_: "Asana changes only for a miss" becomes "Asana mirrors the approved
  build plan", and the analyst still approves before any write.
- _Plan_ step 3: after the hub posts, create under the dashboard the PR tasks
  (`PR <id> (<dbt|Cube>): <scope>`, owner, due), decision tasks, Confirm items,
  the 2 holders and the Validate task; set blocked-by links; move the hub's
  synced task under the dashboard; move each row to its PR or holder and keep
  its kind tag; remove its stage links. Ownership and due-date rules from the
  spec's _Rules_, verbatim in meaning.
- _Build_: a new first step, the sweep; a new step after opening a PR,
  promotion.
- _Finish_: a dashboard's due date moving re-runs ownership.

- [ ] **Step 3: Lint**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/cube-builder/SKILL.md </dev/null`
Expected: no findings beyond formatting.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/cube-builder/SKILL.md
git commit -m "docs(claude): the cube builder keeps each dashboard's plan in Asana"
```

### Task 6: Migrate Literacy (Asana, gid `1213823922716082`)

Runs only after Tasks 1 to 4 have shipped.

- [ ] **Step 1: Baseline** Save Literacy's page counts from the live `data.js`
      (Task 4's `jq`).
- [ ] **Step 2: Rename the PR tasks to carry their type** where missing: L1
      (`1219976000477262`) becomes
      `PR L1 (Cube): DIBELS measure percentile on student_assessment_scores_view`.
- [ ] **Step 3: Create the holders** `Already in Cube` and `Deferred` under
      Literacy.
- [ ] **Step 4: Move rows.** Every open row whose `Used by:` names Literacy and
      whose earliest-due dashboard is Literacy moves to its PR task:
      `fct_sight_words` rows to SW2 (`1220821807397663`),
      `fct_dibels_progress_monitoring` rows to PM4 (`1220818762959472`), "DIBELS
      measure percentile" (`1219284586585436`) to L1. Done rows that Literacy
      owns go to `Already in Cube`; deferred ones to `Deferred`. Remove each
      moved row's links to `mart:` / `cube:` / `view:` stages.
- [ ] **Step 5: Close emptied stages and tables** per the spec's _Stage
      subtasks_ rule. A stage with work left becomes a PR task under Literacy.
- [ ] **Step 6: Sync and compare.** Run the sync script with
      `--only 1213823922716082` (preview, then `--apply`), dispatch the
      generator, and diff Literacy's counts against Step 1. Expected: identical.

### Task 7: Pilot STAT (gid `1213823789082035`)

- [ ] **Step 1:** Run the updated cube-builder skill for STAT through its
      _Inventory_, _No duplicates_ and _Plan_ sections. The analyst approves the
      hub draft before anything posts.
- [ ] **Step 2:** Apply _Plan_ step 3 to STAT, then repeat Task 6 Steps 5 and 6
      with STAT's gid. Builds DDI Suite or Literacy already ship become Confirm
      items.
