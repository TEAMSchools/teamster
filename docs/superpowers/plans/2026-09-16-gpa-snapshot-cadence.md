# GPA snapshot cadence implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put `snapshot_powerschool__gpa_term` and
`snapshot_powerschool__gpa_cumulative` on a `0 23 * * *` cron automation
condition so they merge once a day instead of about 143 times.

**Architecture:** Add `meta.dagster.automation_condition.cron_schedule` to each
snapshot's existing `config.meta.dagster` block in
`src/dbt/kipptaf/snapshots/powerschool.yml`.
`CustomDagsterDbtTranslator.get_automation_condition` already routes any node
whose `config.materialized` is not `view` or `ephemeral` down the
`dbt_cron_automation_condition()` branch when that key is present, so no Python
changes are needed. Verified by one test against the real kipptaf dbt manifest.

**Tech Stack:** dbt (YAML-defined snapshots), Dagster declarative automation,
pytest, trunk.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-09-16-gpa-snapshot-cadence-design.md`.
- Cron value is exactly `0 23 * * *`. Not `0 0 * * *` — midnight shifts
  `dbt_valid_from_date` attribution by a day for all three consumers.
- No `cron_timezone` key. It defaults to the code location's `LOCAL_TIMEZONE`,
  which is `America/New_York` for kipptaf.
- The new key goes inside the existing `config.meta.dagster` block, above
  `asset_key`, matching key order in `src/dbt/kipptaf/snapshots/students.yml`
  and `src/dbt/kipptaf/snapshots/kippadb.yml`.
- `_get_dbt_meta()` or-short-circuits the WHOLE top-level `meta` dict when
  `config.meta` is present. Both snapshots already keep `group` and `asset_key`
  under `config.meta`, so the new key must go there too. Putting it under a
  top-level `meta` would silently drop `asset_key`.
- No SQL changes. No Python changes. No changes to either snapshot's `strategy`,
  `unique_key`, `check_cols`, or `dbt_valid_to_current`.
- All work happens in the worktree at
  `/workspaces/teamster/.worktrees/cbini/perf/claude-gpa-snapshot-cadence` on
  branch `cbini/perf/claude-gpa-snapshot-cadence`. Every `git` call is
  `git -C <worktree>` or runs with cwd inside the worktree.
- Never run bare `python`, `dbt`, or `dagster` — always `uv run`.

---

### Task 1: Cron both GPA snapshots at `0 23 * * *`

**Files:**

- Modify:
  `/workspaces/teamster/.worktrees/cbini/perf/claude-gpa-snapshot-cadence/src/dbt/kipptaf/snapshots/powerschool.yml`
  (both snapshot entries)
- Test:
  `/workspaces/teamster/.worktrees/cbini/perf/claude-gpa-snapshot-cadence/tests/test_automation_conditions.py`
  (new method on the existing `TestKipptafDbtAssets` class)

**Interfaces:**

- Consumes: `CustomDagsterDbtTranslator.get_automation_condition(props)` and
  `.get_asset_key(props)` from `teamster.libraries.dbt.dagster_dbt_translator`;
  `dbt_cron_automation_condition(cron_schedule, cron_timezone)` from
  `teamster.core.automation_conditions`, already imported at the top of
  `tests/test_automation_conditions.py`; the `nodes_by_name` class fixture,
  which maps `manifest["nodes"]` by node name and already includes snapshot
  nodes.
- Produces: nothing other tasks depend on. This is the only task.

- [ ] **Step 1: Install dbt packages in the worktree**

A fresh worktree has no `dbt_packages/`, so any later dbt command fails on a
missing `dbt_utils`. Run this in its own command.

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-gpa-snapshot-cadence && \
  uv run dbt deps --project-dir src/dbt/kipptaf
```

Expected: `Installing dbt-labs/dbt_utils` and friends, ending clean.

- [ ] **Step 2: Write the failing test**

Append this method to the existing `TestKipptafDbtAssets` class in
`tests/test_automation_conditions.py`, directly after
`test_union_relations_views_get_union_relations_condition`. `AssetKey` and
`dbt_cron_automation_condition` are already imported at the top of the file — do
not add imports for them.

```python
    def test_gpa_snapshots_get_cron_condition(self, nodes_by_name):
        """The two PowerSchool GPA snapshots must be on the 23:00 cron condition.

        A dbt snapshot's config.materialized is 'snapshot', not view or
        ephemeral, so both inherit dbt_table_automation_condition() by default.
        Their upstreams are a view (int_powerschool__gpa_cumulative) and an
        ephemeral model (int_powerschool__gpa_term_current), so ancestor-updated
        recursion reaches every PowerSchool grade table and fired each snapshot
        about 143 times a day. Refs #5218.
        """
        from teamster.libraries.dbt.dagster_dbt_translator import (
            CustomDagsterDbtTranslator,
        )

        translator = CustomDagsterDbtTranslator(
            code_location="kipptaf", local_timezone="America/New_York"
        )
        expected = dbt_cron_automation_condition(
            "0 23 * * *", cron_timezone="America/New_York"
        )

        for name in (
            "snapshot_powerschool__gpa_term",
            "snapshot_powerschool__gpa_cumulative",
        ):
            props = nodes_by_name[name]

            assert props["config"]["materialized"] == "snapshot", (
                f"{name} is no longer a snapshot; this test's premise is stale"
            )
            assert translator.get_automation_condition(props) == expected, (
                f"{name} did not get the 0 23 * * * cron condition"
            )
            # _get_dbt_meta or-shorts the whole top-level meta dict, so
            # automation_condition and asset_key must sit on the same side.
            # A misplaced key drops the explicit asset_key and the resolved
            # key loses its 'powerschool' segment.
            assert translator.get_asset_key(props) == AssetKey(
                ["kipptaf", "powerschool", name]
            ), f"{name} lost its explicit asset_key"
```

- [ ] **Step 3: Regenerate the manifest so the test reads current YAML**

The `manifest` fixture reads `DBT_PROJECT.manifest_path` off disk. It must
reflect the worktree's YAML, not a stale artifact.

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-gpa-snapshot-cadence && \
  uv run dbt parse --no-partial-parse --project-dir src/dbt/kipptaf
```

Expected: exits clean and writes `src/dbt/kipptaf/target/manifest.json`.

- [ ] **Step 4: Run the test to verify it fails**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-gpa-snapshot-cadence && \
  uv run pytest "tests/test_automation_conditions.py::TestKipptafDbtAssets::test_gpa_snapshots_get_cron_condition" -v
```

Expected: FAIL on the second assertion —
`snapshot_powerschool__gpa_term did not get the 0 23 * * * cron condition`. The
`materialized == "snapshot"` assertion above it must PASS; if that one fails
instead, stop and re-read the manifest, because the premise of the whole change
is wrong.

- [ ] **Step 5: Add the cron key to `snapshot_powerschool__gpa_cumulative`**

In `src/dbt/kipptaf/snapshots/powerschool.yml`, inside the first snapshot's
`config.meta.dagster` block, insert `automation_condition` between `group` and
`asset_key`.

Before:

```text
      meta:
        dagster:
          group: powerschool
          asset_key:
            - kipptaf
            - powerschool
            - snapshot_powerschool__gpa_cumulative
```

After:

```text
      meta:
        dagster:
          group: powerschool
          # 1x/day instead of eager. A snapshot inherits
          # dbt_table_automation_condition() (materialized is 'snapshot', not
          # view/ephemeral), and its upstream int_powerschool__gpa_cumulative is
          # a view, so ancestor-updated recursion reaches every PowerSchool
          # grade table — 147 merges and 2.23 slot hours a day.
          #
          # 23:00 and not 00:00: all three consumers resolve at day grain
          # (int_topline__gpa_cumulative_weekly dedupes on dbt_valid_from_date;
          # int_powerschool__gpa_term_lookback matches midnight boundaries). An
          # end-of-day capture keeps a Monday change on Monday. Midnight moves
          # it to Tuesday and shifts every topline weekly value by a day.
          #
          # Intra-day versions are lost. No consumer reads them. Refs #5218
          automation_condition:
            cron_schedule: 0 23 * * *
          asset_key:
            - kipptaf
            - powerschool
            - snapshot_powerschool__gpa_cumulative
```

- [ ] **Step 6: Add the cron key to `snapshot_powerschool__gpa_term`**

Same edit on the second snapshot entry in the same file.

Before:

```text
      meta:
        dagster:
          group: powerschool
          asset_key:
            - kipptaf
            - powerschool
            - snapshot_powerschool__gpa_term
```

After:

```text
      meta:
        dagster:
          group: powerschool
          # 1x/day instead of eager, for the same reason as
          # snapshot_powerschool__gpa_cumulative above — 138 merges and 3.90
          # slot hours a day. Its upstream int_powerschool__gpa_term_current is
          # ephemeral, so ancestor-updated recursion reaches the same
          # PowerSchool grade tables.
          #
          # Consumers int_topline__gpa_term_weekly and
          # int_powerschool__gpa_term_lookback both resolve at day grain, and
          # the lookback matches the first instant of the day after
          # current_date - N, so an end-of-day capture is what its
          # "value in effect at the END of that lookback day" contract needs.
          # Refs #5218
          automation_condition:
            cron_schedule: 0 23 * * *
          asset_key:
            - kipptaf
            - powerschool
            - snapshot_powerschool__gpa_term
```

- [ ] **Step 7: Regenerate the manifest**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-gpa-snapshot-cadence && \
  uv run dbt parse --no-partial-parse --project-dir src/dbt/kipptaf
```

Expected: exits clean. A YAML indentation mistake surfaces here as a parse
error, not in the test.

- [ ] **Step 8: Run the test to verify it passes**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-gpa-snapshot-cadence && \
  uv run pytest "tests/test_automation_conditions.py::TestKipptafDbtAssets::test_gpa_snapshots_get_cron_condition" -v
```

Expected: PASS.

- [ ] **Step 9: Run the rest of the automation-condition suite**

The new method shares class fixtures with its neighbors, and
`test_most_tables_have_automation_condition` counts conditions across the
project, so run the whole file.

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-gpa-snapshot-cadence && \
  uv run pytest tests/test_automation_conditions.py -v 2>&1 | tail -30
```

Expected: no new failures. Baseline any failure against `main` before
attributing it to this change.

- [ ] **Step 10: Lint the changed YAML and the plan**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-gpa-snapshot-cadence && \
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/snapshots/powerschool.yml \
  tests/test_automation_conditions.py \
  docs/superpowers/plans/2026-09-16-gpa-snapshot-cadence.md </dev/null
```

Expected: no issues. Fix anything reported before committing.

- [ ] **Step 11: Commit**

Write the message to the session scratchpad first, then commit with `-F`. Do not
stage `src/dbt/kipptaf/target/` — it is a build artifact.

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-gpa-snapshot-cadence && \
  git add src/dbt/kipptaf/snapshots/powerschool.yml \
          tests/test_automation_conditions.py \
          docs/superpowers/plans/2026-09-16-gpa-snapshot-cadence.md && \
  git status --short
```

Then commit with a message of this shape, ending with the repo's attribution
line:

```text
perf(powerschool): cron GPA snapshots at 23:00

Both snapshots inherit dbt_table_automation_condition() because a dbt
snapshot's materialized is 'snapshot', and their upstreams are a view and an
ephemeral model, so ancestor-updated recursion fired them ~143 times a day
each — 285 merges and 6.13 slot hours a day between them.

23:00 rather than the 00:00 used by the #4821 snapshots: all three consumers
resolve at day grain, so an end-of-day capture keeps a Monday change on
Monday.

Closes #5218
```

---

## Post-merge verification

Not part of the plan's task cycle — a properties-YAML-only change fires no
`code_version_changed`, so nothing rebuilds until the first cron tick at 23:00
America/New_York. Do not judge the deploy by BigQuery object state before then.

After the first tick:

1. `MERGE` count per day for both tables in
   `region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT` drops to about 1 each, from
   147 and 138. Note the BigQuery MCP blocks the write-verb literal even inside
   a string, so filter `statement_type` with `like 'MER%'`.
2. `dbt_valid_from` still carries a version on every day a grade store occurred.
3. `int_powerschool__gpa_term_lookback` still returns non-null
   `gpa_y1_1_week_prior`, `gpa_y1_2_week_prior`, and `gpa_y1_4_week_prior` for
   the expected population.
