# Stored test failures: replace without dropping — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop concurrent dbt runs from failing on stored-failure relations by
replacing them without deleting them first, in all 5 `kipp*` projects.

**Architecture:** A new macro-only local dbt package, `dbt_overrides`, holds one
patched copy of dbt's built-in `test` materialization for BigQuery. Each `kipp*`
project installs the package and adds a root stub that returns the package
macro, because dbt 1.12 ignores a package override of a built-in materialization
without one. A pytest drift guard ties the copy to the installed dbt-adapters
source.

**Tech Stack:** dbt-core 1.12 / dbt-bigquery, Jinja materializations, pytest,
GitHub Actions.

**Spec:**
`docs/superpowers/specs/2026-11-04-store-failures-replace-race-design.md`

## Global Constraints

- All 5 projects: `kipptaf`, `kippnewark`, `kippcamden`, `kippmiami`,
  `kipppaterson`.
- The package lives at `src/dbt/dbt_overrides/` with dbt project name
  `dbt_overrides`.
- The only behavior change: drop the old relation only when
  `old_relation.type != target_relation.type`. Everything else stays verbatim
  from the installed
  `dbt/include/global_project/macros/materializations/tests/test.sql`.
- Root stubs return `dbt_overrides.materialization_test_bigquery()`. The macro
  name format is `materialization_<name>_<adapter>`
  (`dbt_common/utils/jinja.py`, `get_materialization_macro_name`).
- dbt resolves the test materialization with the ROOT project name
  (`dbt/task/test.py`, `self.config.project_name`), so tests from source
  packages (for example powerschool tests in kippnewark) use the root stub. No
  per-package stub is needed.
- No warehouse writes outside your own dev schemas. Never `--target prod` or
  `--target staging`.
- Always `uv run`. Reach the worktree by absolute path:
  `/workspaces/teamster/.claude/worktrees/cbini/fix/claude-store-failures-replace-race`.
  `<abs>` below means that path.
- PR body says `Refs #6254`, never `Closes`. The issue stays open for the 30-day
  zero-recurrence check.

## Review Focus

1. **The type comparison is always true.** If `old_relation.type` is an enum and
   `target_relation.type` a string that never compare equal, the patch still
   drops every time and silently fixes nothing. Task 2 Step 5 checks it
   directly.
2. **Changing `store_failures_as` (view to table).** The old relation must still
   be dropped first, or `create or replace table` fails on an existing view.
   Task 2 Step 6 covers it.
3. **The formatter rewrites the copy.** The pre-commit hook runs sqlfmt on
   `src/dbt/**`. If it reformats the materialization, the drift test fails. Task
   1 Step 6 covers it.
4. **dbt Cloud CI cannot resolve `local: ../dbt_overrides`.** CI builds kipptaf
   alone, and kipptaf has no local package today. The PR's dbt Cloud CI run is
   the check, in Task 4.
5. **Dagster cannot load the project.** `prepare-and-package` must run
   `dbt deps` with the new local package. Task 3 Step 5 covers it.

---

### Task 1: The `dbt_overrides` package and its drift guard

**Files:**

- Create: `src/dbt/dbt_overrides/dbt_project.yml`
- Create: `src/dbt/dbt_overrides/macros/materialization_test.sql`
- Create: `src/dbt/dbt_overrides/CLAUDE.md`
- Test: `tests/test_dbt_overrides.py`

**Interfaces:**

- Produces: the macro `dbt_overrides.materialization_test_bigquery`, which Task
  3's root stubs call. The file path that Task 4's CI step and `paths:` entry
  name.

- [ ] **Step 1: Write the failing drift test** in `tests/test_dbt_overrides.py`.
      Constants: `UPSTREAM` is
      `Path(dbt.include.global_project.__file__).parent / "macros/materializations/tests/test.sql"`.
      `OURS` is
      `Path(__file__).parents[1] / "src/dbt/dbt_overrides/macros/materialization_test.sql"`.
      `PATCHES` is a list of `(upstream_text, our_text)` pairs:

  ```python
  PATCHES = [
      (
          "{%- materialization test, default -%}",
          "{%- materialization test, adapter='bigquery' -%}",
      ),
      (
          "    {% if old_relation %}\n",
          "    {# create or replace swaps a same-type relation in one step;"
          " dropping first leaves a gap a concurrent run can hit #}\n"
          "    {% if old_relation and old_relation.type != target_relation.type %}\n",
      ),
  ]
  ```

  Two tests:
  - `test_upstream_has_each_patch_site_once`: for each pair,
    `UPSTREAM.read_text().count(upstream_text) == 1`, with a failure message
    saying dbt changed the built-in materialization and to re-sync `OURS`.
  - `test_override_matches_patched_upstream`: apply every pair to the upstream
    text with `str.replace(old, new, 1)`. Assert it equals `OURS`'s text from
    the index of `"{%- materialization"` onward. Our file's leading header lines
    are excluded from the comparison.

- [ ] **Step 2: Run it and see it fail**

  Run:
  `cd /workspaces/teamster/.claude/worktrees/cbini/fix/claude-store-failures-replace-race && uv run pytest tests/test_dbt_overrides.py -q 2>&1 | tail -n 15`
  Expected: `test_upstream_has_each_patch_site_once` PASSES, and
  `test_override_matches_patched_upstream` FAILS with `FileNotFoundError` on
  `OURS`.

- [ ] **Step 3: Create the package.** `dbt_project.yml` follows the
      `src/dbt/titan/dbt_project.yml` shape, trimmed to a macro-only package:
      `name: dbt_overrides`, `version: 1.0.0`, `config-version: 2`,
      `require-dbt-version: [">=1.12.0", <2.0.0]`, `profile: integration_tests`,
      `macro-paths: [macros]`, `seed-paths: []`, and no models.

  `macros/materialization_test.sql` starts with these header lines, then the
  upstream file with `PATCHES` applied:

  ```sql
  -- fmt: off
  {#- Fork of dbt-adapters' built-in test materialization: drops the stored-failure
      relation only on a type change. tests/test_dbt_overrides.py fails when the
      built-in changes; re-sync this file from it. Delete with every root stub
      once dbt-labs/dbt#16343 ships. -#}
  ```

  Generate the body from the installed file rather than by hand, for example
  with a one-off `uv run python -c` that applies `PATCHES` and writes the file.
  `CLAUDE.md` is 3 short paragraphs:
  - What the package is.
  - Why every root project needs a stub: the
    `require_explicit_package_overrides_for_builtin_materializations` behavior.
  - How to re-sync the copy when the drift test fails.

- [ ] **Step 4: Run the drift test and see it pass**

  Run:
  `cd /workspaces/teamster/.claude/worktrees/cbini/fix/claude-store-failures-replace-race && uv run pytest tests/test_dbt_overrides.py -q 2>&1 | tail -n 5`
  Expected: `2 passed`.

- [ ] **Step 5: Commit.** Stage the 4 new files by path, then use
      `git -C <worktree> commit` with message
      `fix(dbt): add dbt_overrides test materialization that replaces without dropping`
      and `Refs #6254`. The pre-commit hook runs `trunk fmt`.

- [ ] **Step 6: Confirm the formatter left the copy alone**

  Run:
  `cd /workspaces/teamster/.claude/worktrees/cbini/fix/claude-store-failures-replace-race && git status --short && uv run pytest tests/test_dbt_overrides.py -q 2>&1 | tail -n 3`
  Expected: a clean tree, and `2 passed`. If the hook rewrote the macro and
  `-- fmt: off` did not hold, stop and report it. A formatter ignore for that
  path needs `.trunk/trunk.yaml`, which is hook-protected and goes to the user.

### Task 2: Prove the race and the fix in a throwaway dev project

No repo files. This writes only to your own dev audit schema.

**Files:**

- Create (scratch only):
  `/tmp/claude-1000/-workspaces-teamster/e1c91925-d6d9-48a6-8b51-a63b2c6a6ab5/scratchpad/race_harness/`

**Interfaces:**

- Consumes: `dbt_overrides` from Task 1, through an absolute `local:` path to
  the worktree package.

- [ ] **Step 1: Build the harness project.** Its pieces:
  - A `dbt_project.yml` named `race_harness`. Use the profile and `dev` target
    from `/workspaces/teamster/.dbt/profiles.yml`; read the file for the profile
    name. Set `data_tests: +store_failures: true, +store_failures_as: view`.
  - A `packages.yml` with `- local: <abs worktree>/src/dbt/dbt_overrides`.
  - 40 singular tests, `tests/race_probe_01.sql` through `race_probe_40.sql`,
    each `select 1 as n`. They fail with 1 row, so they write a view.
  - No root stub yet.

  Run `uv run dbt deps` in it.

- [ ] **Step 2: Write `run_race.sh <rounds>`.** Each round starts 2
      `dbt test --threads 8` invocations at once, each with its own
      `--target-path` and `--log-path`. It then counts lines matching
      `Not found: Table` or `Already Exists: Table` in both logs, and prints a
      total per round and overall. Set `DBT_PROFILES_DIR` to
      `/workspaces/teamster/.dbt`.

- [ ] **Step 3: Control run (no stub, dbt's own materialization)**

  Run: `bash run_race.sh 3` (run in the background if it exceeds 120s) Expected:
  at least 1 race error overall. If you get 0, raise to 80 tests and 5 rounds
  once. If it is still 0, record "harness inconclusive" and go on. The BigQuery
  race test on #6254 remains the evidence.

- [ ] **Step 4: Patched run.** Add the root stub,
      `macros/materialization_test.sql`, the same 3 lines Task 3 adds. Then
      re-run `bash run_race.sh 3`.

  Expected: 0 race errors in every round.

- [ ] **Step 5: Check the type comparison directly.** Add a harness macro,
      `check_type_compare`. After the patched run, it gets
      `adapter.get_relation(...)` for `race_probe_01` in the audit schema,
      builds `api.Relation.create(..., type='view')`, and logs
      `old.type != target.type` and `old.type != table_target.type`. Run it with
      `uv run dbt run-operation check_type_compare`.

  Expected: `False` for view versus view, and `True` for view versus table.

- [ ] **Step 6: Type change still works.** Set `store_failures_as='table'` in
      `race_probe_01`'s `config()`, then run
      `uv run dbt test --select race_probe_01`.

  Expected: `WARN 1` or `FAIL 1` with no error, and the relation is now a table.
  Check it with `INFORMATION_SCHEMA.TABLES` through the BigQuery MCP.

- [ ] **Step 7: Record results** (round totals, Steps 5 and 6) in the session
      scratchpad for the PR body. There is no commit.

### Task 3: Install the package and stub in all 5 projects

**Files:**

- Modify:
  `src/dbt/{kipptaf,kippnewark,kippcamden,kippmiami,kipppaterson}/packages.yml`
- Modify: the same 5 projects' `package-lock.yml`, regenerated by `dbt deps`
- Create: `src/dbt/{same 5}/macros/materialization_test.sql`

**Interfaces:**

- Consumes: `dbt_overrides.materialization_test_bigquery` from Task 1.

- [ ] **Step 1: Write a failing resolution check.** This is a scratch script,
      `check_resolution.py <project>`, not a repo test. It loads
      `<project>/target/manifest.json` and finds
      `macro.<project>.materialization_test_bigquery` and
      `macro.dbt_overrides.materialization_test_bigquery`. It exits 0 only if
      both exist. Run it against kipptaf after
      `uv run dbt parse --project-dir <abs>/src/dbt/kipptaf --target dev`.

  Expected: exit 1, because neither exists yet.

- [ ] **Step 2: For each project, add the package and the stub.** Append
      `- local: ../dbt_overrides` to `packages.yml`, keeping the file's existing
      comment style. Create `macros/materialization_test.sql`:

  ```sql
  {#- Use dbt_overrides' test materialization; see src/dbt/dbt_overrides/CLAUDE.md. -#}
  {% materialization test, adapter='bigquery' -%}
      {{ return(dbt_overrides.materialization_test_bigquery()) }}
  {%- endmaterialization %}
  ```

- [ ] **Step 3: Run `uv run dbt deps --project-dir <abs>/src/dbt/<project>` for
      each project, one at a time.**

  Expected: `Installing dbt_overrides` for each, and `package-lock.yml` updated.

- [ ] **Step 4: Run
      `uv run dbt parse --project-dir <abs>/src/dbt/<project>     --target dev`,
      then `check_resolution.py <project>`, for each project.**

  Expected: parse succeeds and the check exits 0 for all 5.

- [ ] **Step 5: Package kipptaf the way Dagster does.**

  Run:
  `cd /workspaces/teamster/.claude/worktrees/cbini/fix/claude-store-failures-replace-race && uv run dagster-dbt project prepare-and-package --file src/teamster/code_locations/kipptaf/__init__.py 2>&1 | tail -n 10`
  Expected: success, with no error about `dbt_overrides`.

- [ ] **Step 6: Run one stored-failure test in a district on the dev target.**
      Pick one cheap powerschool package test in kippnewark. Run
      `uv run dbt test --project-dir <abs>/src/dbt/kippnewark --select <that test>     --target dev --defer --state <abs main-checkout>/src/dbt/kippnewark/target/prod`
      twice in a row. Invoke `dbt-local-dev` first for the defer flags.

  Expected: both runs complete without an execution error. The second run
  replaces the existing view.

- [ ] **Step 7: Commit.** Stage the changed `packages.yml` and
      `package-lock.yml` files with `git add -u`, and the 5 new stubs by path.
      Commit message:
      `fix(dbt): install dbt_overrides test materialization in every kipp project`
      with `Refs #6254`.

### Task 4: CI guard, docs, and PR

**Files:**

- Modify: `.github/workflows/pytest.yaml`
- Modify: `src/dbt/CLAUDE.md` (_Project Dependency Map_)

- [ ] **Step 1: Add a `dbt-overrides` job to `pytest.yaml`.** Model it on the
      `cube-validation` job: checkout, setup-uv with the same pinned SHAs, then
      `uv run pytest tests/test_dbt_overrides.py -q`. Give it a comment saying
      it exists so a dependabot `uv.lock` dbt bump fails when the built-in
      materialization changes. Add `src/dbt/dbt_overrides/**` and
      `tests/test_dbt_overrides.py` to `on.pull_request.paths`.

- [ ] **Step 2: Add 1 or 2 lines to `src/dbt/CLAUDE.md`** under _Project
      Dependency Map_. Every `kipp*` project installs `dbt_overrides` and
      carries a root stub. A new dbt project that stores test failures needs
      both. Details are in `src/dbt/dbt_overrides/CLAUDE.md`.

- [ ] **Step 3: Lint.**

  Run:
  `cd /workspaces/teamster/.claude/worktrees/cbini/fix/claude-store-failures-replace-race && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix .github/workflows/pytest.yaml src/dbt/CLAUDE.md src/dbt/dbt_overrides src/dbt/*/macros/materialization_test.sql src/dbt/*/packages.yml docs/superpowers/plans/2026-11-04-store-failures-replace-race.md </dev/null 2>&1 | tail -n 20`
  Expected: no lint issues. A formatting-only finding is the hook's job.

- [ ] **Step 4: Commit, push, and open the PR.** Write the body from
      `.github/pull_request_template.md`, with `Refs #6254` and Task 2's
      results. Then follow `pr-ci-review`: watch CI and process the
      `claude-review` findings.

  Expected: dbt Cloud CI parses kipptaf with the local package (Review Focus 4),
  the `dbt-overrides` job passes, and the branch deployment loads kipptaf.

- [ ] **Step 5: Draft the dbt-labs/dbt#16343 comment.** Cover the concurrency
      race and its 2 errors, and the BigQuery race-test counts. Leave out
      internal names and test names. Show the draft to the user and post only on
      approval.
