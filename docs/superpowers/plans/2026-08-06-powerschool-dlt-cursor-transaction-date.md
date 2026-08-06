# PowerSchool dlt Intraday Cursor Switch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change the intraday change-detection cursor from `whenmodified` to
`transaction_date` for the three PowerSchool tables that carry both columns, so
in-place updates that do not bump `whenmodified` stop being invisible to the
sensor.

**Architecture:** Pure configuration change. The sensor already reads
`cursor_column` per table from each district's `assets.yaml` and interpolates it
into `SELECT COUNT(*), MAX({cursor_column}) FROM {table_name}`. Changing the
configured value changes the probe with no code change. Ten sibling tables in
the same files already use `transaction_date`.

**Tech Stack:** YAML config consumed by `yaml.safe_load`, Dagster sensors, dlt,
BigQuery, `uv` for Python execution.

## Global Constraints

- Spec:
  `docs/superpowers/specs/2026-08-06-powerschool-dlt-cursor-transaction-date-design.md`
- Issue: [#4754](https://github.com/TEAMSchools/teamster/issues/4754)
- Worktree:
  `/workspaces/teamster/.worktrees/cbini/fix/claude-powerschool-cursor-transaction-date`
- Branch: `cbini/fix/claude-powerschool-cursor-transaction-date`
- Every git command uses
  `git -C /workspaces/teamster/.worktrees/cbini/fix/claude-powerschool-cursor-transaction-date`.
  A bare `git` from the main repo commits to `main`.
- Every Read, Edit, and Write targets the worktree path, not
  `/workspaces/teamster/<path>`. Editing the main checkout silently leaves the
  worktree unchanged.
- Exactly three tables change: `users`, `schoolstaff`, `sectionteacher`. Do not
  touch any other table entry.
- Only `cursor_column` changes. Do not touch `intraday` or `nightly` on any
  entry.
- No Python changes. No new test files.
- The `trunk` binary lives only in the main repo. Invoke it by absolute path
  `/workspaces/teamster/.trunk/tools/trunk` with cwd set to the worktree. If
  that path does not exist, use `~/.cache/trunk/launcher/trunk`.
- `cursor_column: whenmodified` appears 13 times in the Paterson file and 17
  times in each of the Newark and Camden files. Every edit must anchor on the
  preceding `- table_name: <name>` line so it cannot match the wrong table.

---

## File Structure

Three files are modified. No files are created.

| File                                                                              | Change                                                         |
| --------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/config/assets.yaml` | 3 lines: `schoolstaff` L48, `sectionteacher` L56, `users` L88  |
| `src/teamster/code_locations/kippnewark/powerschool/sis/dlt/config/assets.yaml`   | 3 lines: `schoolstaff` L48, `sectionteacher` L56, `users` L104 |
| `src/teamster/code_locations/kippcamden/powerschool/sis/dlt/config/assets.yaml`   | 3 lines: `schoolstaff` L48, `sectionteacher` L56, `users` L104 |

Line numbers are as of branch point `6d58d4607`. Anchor edits on the
`table_name` line rather than trusting the number.

---

### Task 1: Switch the cursor for the three tables across all three districts

**Files:**

- Modify:
  `src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/config/assets.yaml:48,56,88`
- Modify:
  `src/teamster/code_locations/kippnewark/powerschool/sis/dlt/config/assets.yaml:48,56,104`
- Modify:
  `src/teamster/code_locations/kippcamden/powerschool/sis/dlt/config/assets.yaml:48,56,104`
- Test: none. Verified by the inline assertion script in Step 1, which is run
  from the shell and never committed.

**Interfaces:**

- Consumes: nothing from earlier tasks. This is the first task.
- Produces: the three config files in their final state. Task 2 pushes them;
  Task 3 verifies their runtime effect. No Python symbols are added or changed.

- [ ] **Step 1: Write the verification script and watch it fail**

This replaces a unit test. It parses each config exactly as `sensors.py` does
and asserts the three tables cursor on `transaction_date`. Write it to the
scratch directory so it is never committed.

Write `/workspaces/teamster/.claude/scratch/verify_cursors.py`:

```python
import pathlib
import sys

import yaml

TARGET = {"users", "schoolstaff", "sectionteacher"}
WORKTREE = pathlib.Path(
    "/workspaces/teamster/.worktrees/cbini/fix/claude-powerschool-cursor-transaction-date"
)

failures = []

for loc in ["kipppaterson", "kippnewark", "kippcamden"]:
    path = (
        WORKTREE
        / "src/teamster/code_locations"
        / loc
        / "powerschool/sis/dlt/config/assets.yaml"
    )
    assets = yaml.safe_load(path.read_text())["assets"]

    seen = set()
    for entry in assets:
        name = entry["table_name"]
        if name not in TARGET:
            continue
        seen.add(name)

        if entry["cursor_column"] != "transaction_date":
            failures.append(f"{loc}.{name}: cursor is {entry['cursor_column']!r}")
        if entry["intraday"] is not True:
            failures.append(f"{loc}.{name}: intraday changed to {entry['intraday']!r}")
        if entry["nightly"] is not False:
            failures.append(f"{loc}.{name}: nightly changed to {entry['nightly']!r}")

    missing = TARGET - seen
    if missing:
        failures.append(f"{loc}: missing table entries {sorted(missing)}")

    # Guard against a stray edit: count how many entries still cursor on
    # whenmodified across the whole file. Paterson has 24 before the change and
    # 21 after; Newark and Camden have 29 before and 26 after.
    remaining = sum(1 for e in assets if e["cursor_column"] == "whenmodified")
    expected = 21 if loc == "kipppaterson" else 26
    if remaining != expected:
        failures.append(
            f"{loc}: {remaining} tables still cursor on whenmodified, expected {expected}"
        )

if failures:
    print("FAIL")
    for f in failures:
        print(f"  {f}")
    sys.exit(1)

print("PASS: all three tables cursor on transaction_date in all three districts")
```

- [ ] **Step 2: Run it to confirm it fails before any edit**

```bash
uv run --active python /workspaces/teamster/.claude/scratch/verify_cursors.py
```

Expected: exit 1, and nine `cursor is 'whenmodified'` lines — three per
district. If you see fewer than nine, stop: the branch is not at the expected
baseline.

- [ ] **Step 3: Edit the three Paterson entries**

In
`/workspaces/teamster/.worktrees/cbini/fix/claude-powerschool-cursor-transaction-date/src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/config/assets.yaml`,
make three separate edits. Each `old_string` includes the `table_name` line so
the match is unique.

Edit 1:

```text
  - table_name: schoolstaff
    cursor_column: whenmodified
```

becomes:

```text
  - table_name: schoolstaff
    cursor_column: transaction_date
```

Edit 2:

```text
  - table_name: sectionteacher
    cursor_column: whenmodified
```

becomes:

```text
  - table_name: sectionteacher
    cursor_column: transaction_date
```

Edit 3:

```text
  - table_name: users
    cursor_column: whenmodified
```

becomes:

```text
  - table_name: users
    cursor_column: transaction_date
```

- [ ] **Step 4: Repeat the same three edits in the Newark config**

Same three edits, in
`/workspaces/teamster/.worktrees/cbini/fix/claude-powerschool-cursor-transaction-date/src/teamster/code_locations/kippnewark/powerschool/sis/dlt/config/assets.yaml`.
The `table_name` anchors are identical; only the file path differs.

- [ ] **Step 5: Repeat the same three edits in the Camden config**

Same three edits, in
`/workspaces/teamster/.worktrees/cbini/fix/claude-powerschool-cursor-transaction-date/src/teamster/code_locations/kippcamden/powerschool/sis/dlt/config/assets.yaml`.

- [ ] **Step 6: Run the verification script to confirm it passes**

```bash
uv run --active python /workspaces/teamster/.claude/scratch/verify_cursors.py
```

Expected:
`PASS: all three tables cursor on transaction_date in all three districts`

If the `still cursor on whenmodified` guard fires, an edit hit the wrong table.
Inspect the diff before continuing.

- [ ] **Step 7: Confirm the diff is exactly nine lines**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-powerschool-cursor-transaction-date diff --stat
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-powerschool-cursor-transaction-date diff
```

Expected: `3 files changed, 9 insertions(+), 9 deletions(-)`. Every changed line
is a `cursor_column:` line. If any other line appears in the diff, revert it.

- [ ] **Step 8: Confirm the sensor builds its table list from the new config**

This exercises the real code path in `sensors.py` without needing a dbt
manifest.

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-powerschool-cursor-transaction-date && \
uv run --active python -c "
import pathlib, yaml
from teamster.libraries.dlt.powerschool.assets import PowerSchoolTable
p = pathlib.Path('src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/config/assets.yaml')
tables = [PowerSchoolTable(name=a['table_name'], cursor_column=a['cursor_column'])
          for a in yaml.safe_load(p.read_text())['assets'] if a['intraday']]
print(f'{len(tables)} intraday tables')
print([t for t in tables if t.name in ('users','schoolstaff','sectionteacher')])
"
```

Expected: `37 intraday tables`, and all three printed tables show
`cursor_column='transaction_date'`.

- [ ] **Step 9: Optionally run the PR template's Dagster checks**

The PR template asks for `dagster definitions validate` and
`pytest tests/test_dagster_definitions.py` on modified code locations. Both need
a dbt manifest per location, which a fresh worktree does not have. If you want
them, generate the manifests first:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-powerschool-cursor-transaction-date && \
uv run dagster-dbt project prepare-and-package \
  --file src/teamster/code_locations/kipppaterson/__init__.py
```

Then:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-powerschool-cursor-transaction-date && \
uv run dagster definitions validate \
  -m teamster.code_locations.kipppaterson.definitions
```

This is optional. Step 8 already exercises the exact code path this change
affects, and `definitions validate` is prone to environment-related false
failures in the codespace. If you skip it, say so in the PR rather than ticking
the box.

- [ ] **Step 10: Lint the three changed files**

yamllint runs at pre-push and in CI, not in the pre-commit format hook, so check
it explicitly.

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-powerschool-cursor-transaction-date && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/config/assets.yaml \
  src/teamster/code_locations/kippnewark/powerschool/sis/dlt/config/assets.yaml \
  src/teamster/code_locations/kippcamden/powerschool/sis/dlt/config/assets.yaml </dev/null
```

Expected: `No issues`. A `✖ N unformatted files` result is fine — the pre-commit
format hook fixes it at commit time.

- [ ] **Step 11: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-powerschool-cursor-transaction-date \
  add src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/config/assets.yaml \
      src/teamster/code_locations/kippnewark/powerschool/sis/dlt/config/assets.yaml \
      src/teamster/code_locations/kippcamden/powerschool/sis/dlt/config/assets.yaml

git -C /workspaces/teamster/.worktrees/cbini/fix/claude-powerschool-cursor-transaction-date \
  commit -m "fix(dagster): cursor powerschool users, schoolstaff, sectionteacher on transaction_date

The intraday sensor signature is COUNT(*) plus MAX(cursor_column), so an
in-place UPDATE that does not advance the cursor is invisible. Confirmed live
on Paterson users: 10 rows changed homeschoolid, 0 changed whenmodified, and
the probe signature matched the stored baseline exactly.

These three tables carry both whenmodified and transaction_date. The ten other
intraday tables in the same configs already cursor on transaction_date.

Closes #4754

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

If the commit hook rejects the message, write it to
`.claude/scratch/commit-msg.txt` with the Write tool and use
`git -C <worktree> commit -F .claude/scratch/commit-msg.txt`.

---

### Task 2: Open the pull request

**Files:**

- Modify: none. This task only pushes and opens the PR.

**Interfaces:**

- Consumes: the commit produced by Task 1.
- Produces: a PR number, used by Task 3 to confirm the merge landed.

- [ ] **Step 1: Push the branch**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-powerschool-cursor-transaction-date push
```

The branch already tracks its remote, so a bare `push` is correct here. The
pre-push hook runs `trunk check`; if it fails, fix and re-push before opening
the PR.

- [ ] **Step 2: Confirm the pushed diff against main is only the config and the
      spec**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-powerschool-cursor-transaction-date \
  diff --stat origin/main...HEAD
```

Expected: four files — the three `assets.yaml` plus the spec markdown from the
brainstorming commit. Nothing else.

- [ ] **Step 3: Open the PR**

Use `mcp__github__create_pull_request` with base `main`, head
`cbini/fix/claude-powerschool-cursor-transaction-date`, and title:

```text
fix(dagster): cursor powerschool users, schoolstaff, sectionteacher on transaction_date
```

Open it ready-for-review, not draft — `deploy-prod-<location>.yaml` gates the
branch deploy on a non-draft PR.

Body:

```markdown
# Pull Request

## Summary & Motivation

> "When merged, this pull request will..."

Change the intraday change-detection cursor from `whenmodified` to
`transaction_date` for `users`, `schoolstaff`, and `sectionteacher` in all three
PowerSchool districts.

The intraday sensor detects change with `COUNT(*)` plus `MAX(cursor_column)`, so
an in-place UPDATE that does not advance the cursor is invisible. These three
tables are `intraday: true` with `nightly: false`, so there is no full-refresh
backstop and the staleness persists indefinitely.

Confirmed live against PowerSchool Paterson: 10 staff rows had `homeschoolid`
corrected in PowerSchool, 0 of them advanced `whenmodified`, and the probe
signature was byte-identical to the stored baseline. `transaction_date` moved on
all 10. Across all three districts, every `users` row modified in 2026 carries a
`transaction_date` at or after its `whenmodified` — 284 of 284.

These three tables are the only exposed tables carrying both columns. The other
ten intraday tables in the same configs, including the four largest, already
cursor on `transaction_date`. Tables with only `whenmodified` are deliberately
untouched: no defect has been demonstrated for them.

This self-remediates. The stored baseline holds a `whenmodified` value, so the
first probe after deploy returns a differing signature and each table reloads
once, clearing the accumulated drift with no manual run.

Design:
`docs/superpowers/specs/2026-08-06-powerschool-dlt-cursor-transaction-date-design.md`

Closes #4754

## AI Assistance

Claude investigated the root cause, ran the live read-only comparison against
PowerSchool, and authored the spec, plan, and config change. Scope was
human-directed: limiting the fix to tables with a demonstrated defect and a
better cursor already available, and dropping a config parity test from scope.

## Self-review

### General

- [x] Review the **Claude Code Review** comment posted on this PR

### Dagster

- [x] Config-only change consumed by `yaml.safe_load`; no Python modified
- [x] Verified the sensor builds `PowerSchoolTable` with the new cursor for all
      three tables

## CI checks

- [ ] **Trunk** — passes
- [ ] **dbt Cloud** — passes. Note this passes trivially: no dbt models are
      touched, so `state:modified+` selects nothing. Not validation.
- [ ] **Dagster Cloud** — passes for all three affected locations
```

Avoid `&`, `"`, and angle-bracket tokens in the title and in code spans — the
GitHub MCP write tools sanitize them even inside backticks.

- [ ] **Step 4: Read the stored PR body back and confirm it is intact**

```bash
gh api repos/TEAMSchools/teamster/pulls/<PR_NUMBER> --jq .body
```

The MCP read tools also sanitize on output, so verify with raw `gh api`, not
`pull_request_read`.

- [ ] **Step 5: Wait for CI and confirm both surfaces are green**

```bash
gh pr checks <PR_NUMBER> --json name,bucket,state
```

CI lives on two disjoint surfaces: dbt Cloud is a commit status, while Trunk,
CodeQL, and `claude` are check runs. `gh pr checks` covers both. The
`dagster-cloud-deploy / deploy` check emits one same-named run per code location
— wait for all of them to reach a terminal conclusion.

Note that dbt Cloud CI will pass trivially: this PR touches no dbt models, so
`state:modified+` selects nothing. That is not validation.

---

### Task 3: Verify the fix in production after merge

Do not start this task until the PR is merged and the Dagster code locations
have redeployed. The three tables reload on the first sensor tick after deploy;
ticks run every 15 minutes.

**Files:**

- Modify: none. This task is verification only.

**Interfaces:**

- Consumes: the merged change from Task 2.
- Produces: confirmation for the issue thread. No code artifacts.

- [ ] **Step 1: Confirm the code locations reloaded with the merge commit**

Use `mcp__dagster__get_location_load_history` for `kipppaterson`, and confirm
the new commit shows `LOADED`.

- [ ] **Step 2: Confirm the sensor selected the three tables instead of
      skipping**

```text
mcp__dagster__get_tick_history(
  name="kipppaterson__powerschool__dlt__intraday_sensor",
  repository_location_name="kipppaterson",
  limit=5,
)
```

Expected: a `SUCCESS` tick whose `requestedAssetKeys` include
`kipppaterson/powerschool/sis/users`,
`kipppaterson/powerschool/sis/schoolstaff`, and
`kipppaterson/powerschool/sis/sectionteacher`. This is the self-remediation
described in the spec: the stored baseline holds a `whenmodified` value, the new
probe returns a `transaction_date` value, so the signatures differ and all three
tables are selected once.

If ticks still report `no change across 37 probed tables`, the deploy has not
landed yet. Wait for the next tick rather than launching a run.

- [ ] **Step 3: Confirm the drift cleared in BigQuery**

Check the invariant rather than a hardcoded row list: no active Paterson staff
member should have a warehouse `homeschoolid` that disagrees with their ADP home
school.

```sql
with sr as (
  select
    powerschool_teacher_number,
    home_work_location_powerschool_school_id as adp_school
  from `teamster-332318.kipptaf_people.int_people__staff_roster`
  where assignment_status = 'Active'
    and home_work_location_dagster_code_location = 'kipppaterson'
    and (home_department_name != 'Data' or home_department_name is null)
)
select count(*) as still_mismatched
from sr
inner join `teamster-332318.kipptaf_powerschool.stg_powerschool__users` as u
  on sr.powerschool_teacher_number = u.teachernumber
  and u._dbt_source_project = 'kipppaterson'
where u.homeschoolid != sr.adp_school
```

Before the fix this returned 10. Expected after: 0, or 1 if the one ADP-side
case has not been corrected in Workday — that row's ADP school is itself wrong,
so it is a People Ops fix, not a pipeline one.

This query names no individual identifiers. The ten specific rows are recorded
in the investigation artifacts under `.claude/scratch/` and the SDD workspace,
both git-ignored; do not copy them into this file, the issue, or the PR.

- [ ] **Step 4: Confirm the affected staff returned to the extract**

Wait for the dbt automation to rebuild `stg_powerschool__users`, then:

```sql
select count(*) as paterson_teachers
from `teamster-332318.kipppaterson_extracts.rpt_powerschool__autocomm_teachers`
```

Compare against the pre-fix count. Expected: up to 10 more rows for Paterson.

- [ ] **Step 5: Re-measure the network-wide mismatch and update the issue**

The 122 figure in #4754 was measured against the stale warehouse copy and is an
upper bound. Re-run it now that all three districts have reloaded:

```sql
with sr as (
  select
    powerschool_teacher_number,
    home_work_location_powerschool_school_id as adp_school,
    home_work_location_dagster_code_location as loc
  from `teamster-332318.kipptaf_people.int_people__staff_roster`
  where assignment_status = 'Active'
    and (home_department_name != 'Data' or home_department_name is null)
)
select
  sr.loc,
  countif(u.teachernumber is not null and u.homeschoolid != sr.adp_school) as mismatched
from sr
left join `teamster-332318.kipptaf_powerschool.stg_powerschool__users` as u
  on sr.powerschool_teacher_number = u.teachernumber
  and sr.loc = u._dbt_source_project
group by sr.loc
order by sr.loc
```

Post the before and after counts as a comment on #4754. Report counts only —
never `teachernumber` or `dcid` values, which are employee identifiers.

- [ ] **Step 6: Confirm the steady-state reload cadence is sane**

Raised in review on PR #4757. `transaction_date` moved on 105 of 219 Paterson
`users` rows between the stored baseline and the live probe, which would be a
problem if it advanced on most 15-minute ticks: these tables load
`write_disposition="replace"` behind a per-district pool at limit 1, so constant
reloading would compete with the large `transaction_date` tables.

Measurement during the investigation says it does not. Live
`MAX(transaction_date)` read `2026-08-06T07:17:33` at both 16:12Z and 17:11Z —
unchanged across roughly 40 consecutive ticks. The column advances in discrete
batches, not continuously, so the signature is stable between batches.

Confirm that holds in production over a longer window than the first tick:

```text
mcp__dagster__get_tick_history(
  name="kipppaterson__powerschool__dlt__intraday_sensor",
  repository_location_name="kipppaterson",
  limit=100,
)
```

Count how many ticks selected any of the three tables. Expected: a small
fraction, clustered around the batch stamping. If instead they are selected on
most ticks, that is a real regression — open a follow-up issue rather than
reverting, since the correctness fix still stands.

- [ ] **Step 7: Clean up the throwaway artifacts**

```bash
rm -f /workspaces/teamster/tests/assets/test_zz_ps_users_probe.py \
      /workspaces/teamster/tests/assets/test_zz_ps_users_drift.py \
      /workspaces/teamster/.claude/scratch/verify_cursors.py
```

These are untracked in the main checkout and were only diagnostic. Confirm with
`git -C /workspaces/teamster status --short` that nothing remains.

- [ ] **Step 8: Remove the worktree**

```bash
git -C /workspaces/teamster worktree remove \
  /workspaces/teamster/.worktrees/cbini/fix/claude-powerschool-cursor-transaction-date
```
