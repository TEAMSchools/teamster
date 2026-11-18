# ADP Staging Failed-Deps Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** `stg_adp_workforce_now__workers` does not build while any ADP workers
partition's latest attempt is failed, and builds once that partition is rerun.

**Architecture:** A new builder in `core/automation_conditions.py` ANDs a
negated `any_deps_match(execution_failed())` onto any condition. The dbt
translator applies it to table models whose meta sets
`dagster.automation_condition.block_on_failed_deps: true`, after it picks the
cron or table condition. The staging model opts in through its properties YAML.
The two roster tables drop the ADP freshness policy.

**Tech Stack:** Dagster 1.13 `AutomationCondition`, dagster-dbt translator, dbt
YAML, pytest with ephemeral instances.

**Spec:** `docs/superpowers/specs/2026-11-02-midnight-preemption-design.md`,
section "Phase 3" and its "Revision 2026-11-03" subsection. The revision
overrides the Phase 3 mechanisms and decision test; the Phase 3 freshness
bullets stand.

## Global Constraints

- Meta key, verbatim:
  `config.meta.dagster.automation_condition.block_on_failed_deps: true`.
- Tables only, like the cron override: a view or ephemeral model carrying the
  key keeps its view or union_relations condition.
- The guard composes with whichever table condition the model gets (plain table
  or cron).
- Guard expression:
  `~AutomationCondition.any_deps_match(AutomationCondition.execution_failed())`.
- No new Dagster+ alert policy. Freshness failures reach `#dagster-alerts`
  through the existing `asset_alert__degraded` policy.
- Freshness: keep `adp_wfn_policy` on `stg_adp_workforce_now__workers`, remove
  it from `int_people__staff_roster` and `int_people__staff_roster_history`,
  leave `stg_people__employee_numbers` as is.
- Always `uv run`. Tests run from the worktree root:
  `/workspaces/teamster/.claude/worktrees/cbini/fix/claude-adp-staging-complete-pull`.
- Stage with `git add -u` (plus `git add <new file>` for a new file). Commit
  messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
  and carry `Refs #6228`.

## Review Focus

1. A failed ADP partition from any date, not just tonight's 45, freezes staging
   until someone reruns it. This is intended ("stay frozen"). Today no partition
   is failed (2,146 of 2,146 materialized as of 2026-11-03), so the deploy does
   not freeze staging on arrival. The reviewer confirms nothing in the guard
   narrows it to a window.
2. The trigger stays armed across held ticks. ADP updates that land while the
   guard holds must still request staging once the guard clears. Task 1's
   evaluation test pins this with two held ticks before the rerun.
3. dbt merges model-level `config.meta` with the folder's
   `+meta: {dagster: {group: adp_workforce_now}}`. If it replaced it instead,
   the asset would change group. Task 2's manifest test asserts both keys.
4. `_get_dbt_meta` or-shorts the whole top-level `meta` dict. The flag goes
   under `config.meta`, the same side as the folder meta. Task 2 asserts the
   asset key is unchanged.
5. The flag on a view is ignored, and the flag composes with a cron override.
   Task 1's translator test pins both.

---

### Task 1: Guard builder and translator flag

**Files:**

- Modify: `src/teamster/core/automation_conditions.py` (new function after
  `dbt_cron_automation_condition`)
- Modify: `src/teamster/libraries/dbt/dagster_dbt_translator.py:56-93`
- Modify: `src/teamster/core/CLAUDE.md` (`automation_conditions.py` section)
- Modify: `src/teamster/libraries/dbt/CLAUDE.md` (translator bullet)
- Test: `tests/test_automation_conditions.py`

**Interfaces:**

- Produces:
  `with_failed_deps_guard(condition: AutomationCondition) -> AutomationCondition`
  in `teamster.core.automation_conditions`. Returns
  `condition & ~AutomationCondition.any_deps_match(AutomationCondition.execution_failed()).with_label("any_deps_failed")`.
  Equality with a second call on an equal input must hold (Task 2 compares with
  `==`).
- Produces: `CustomDagsterDbtTranslator.get_automation_condition` returns
  `with_failed_deps_guard(<cron or table condition>)` for a non-view,
  non-ephemeral model whose `block_on_failed_deps` is truthy.

- [ ] **Step 1: Write the failing evaluation test**

Add `test_table_held_while_dep_partition_failed` near
`test_intacct_extract_partition_aware_on_payroll_update`. Import
`with_failed_deps_guard` in the module's `teamster.core.automation_conditions`
import block.

Setup: `_PARTITIONS = StaticPartitionsDefinition(["2024-01-01", "2024-01-02"])`;
partitioned `workers` asset (`tags=_TABLE_TAG`); two unpartitioned downstream
tables with `deps=[workers]`: `guarded` with
`with_failed_deps_guard(dbt_table_automation_condition())` and `unguarded` with
`dbt_table_automation_condition()`. A second `workers` definition with the same
key raises (pattern: `test_view_requested_on_execution_failure`).

Sequence and assertions:

```python
# baseline: both partitions, then both tables
# evaluate -> result.total_requested == 0
# materialize workers "2024-01-01" OK; materialize failing workers "2024-01-02"
#   with raise_on_error=False
# evaluate (cursor) ->
assert result.get_num_requested(AssetKey("unguarded")) == 1
assert result.get_num_requested(AssetKey("guarded")) == 0
# evaluate again (cursor), still failed ->
assert result.get_num_requested(AssetKey("guarded")) == 0
# materialize working workers "2024-01-02"
# evaluate (cursor) ->
assert result.get_num_requested(AssetKey("guarded")) == 1
```

- [ ] **Step 2: Run it to verify it fails**

Run:
`uv run pytest tests/test_automation_conditions.py -k test_table_held_while_dep_partition_failed -q 2>&1 | tail -n 15`
Expected: collection error,
`ImportError: cannot import name 'with_failed_deps_guard'`.

- [ ] **Step 3: Implement `with_failed_deps_guard` in
      `src/teamster/core/automation_conditions.py`**

Google-style docstring: what it holds back, that an unpartitioned asset over a
partitioned dep checks every partition (not a window), and that the asset's own
triggers stay armed so it builds once the failed partition is rerun.

- [ ] **Step 4: Run it to verify it passes**

Same command as Step 2. Expected: `1 passed`. If the `unguarded` assertion
fails, the scenario is wrong, not the guard: fix the test setup.

- [ ] **Step 5: Write the failing translator test**

Add `test_translator_meta_block_on_failed_deps` after
`test_translator_meta_cron_schedule_override`, with a translator built as
`CustomDagsterDbtTranslator(code_location="kipptaf", local_timezone="America/New_York")`.
Props are
`{"config": {"materialized": ..., "meta": {"dagster": {"automation_condition": {...}}}}}`.

```python
# table + block_on_failed_deps: True
== with_failed_deps_guard(dbt_table_automation_condition())
# table + block_on_failed_deps: True + cron_schedule "0 0 * * *"
== with_failed_deps_guard(
    dbt_cron_automation_condition("0 0 * * *", cron_timezone="America/New_York"))
# view + block_on_failed_deps: True
== dbt_view_automation_condition()
# table + block_on_failed_deps: False
== dbt_table_automation_condition()
```

- [ ] **Step 6: Run it to verify it fails**

Run:
`uv run pytest tests/test_automation_conditions.py -k test_translator_meta_block_on_failed_deps -q 2>&1 | tail -n 15`
Expected: FAIL on the first assertion (plain table condition returned).

- [ ] **Step 7: Apply the flag in `get_automation_condition`**

Restructure the table branch so the cron-or-table condition is computed first,
then wrapped by `with_failed_deps_guard` when
`condition_meta.get("block_on_failed_deps")` is truthy. View, ephemeral and
union_relations paths stay as they are. Extend the existing per-model override
comment to name the new key in one line.

- [ ] **Step 8: Run the whole file**

Run:
`uv run pytest tests/test_automation_conditions.py -q -k "not TestKipptaf" 2>&1 | tail -n 15`
Expected: all pass. (`TestKipptaf*` classes need the manifest; Task 2 runs
them.)

- [ ] **Step 9: Update the two CLAUDE.md files**

`src/teamster/core/CLAUDE.md`: one bullet under the builders list for
`with_failed_deps_guard(condition)`: opted into per model via
`meta.dagster.automation_condition.block_on_failed_deps` (tables only), holds
the model while any dep partition's latest attempt is failed, checks every
partition, rebuilds on rerun. `src/teamster/libraries/dbt/CLAUDE.md`: add the
key to the translator bullet beside `cron_schedule`.

- [ ] **Step 10: Commit**

```bash
git add -u
git commit -m "feat(dagster): hold flagged dbt tables while a dep partition is failed"
```

### Task 2: Opt staging in and drop roster freshness

**Files:**

- Modify:
  `src/dbt/kipptaf/models/adp/workforce_now/api/staging/properties/stg_adp_workforce_now__workers.yml`
- Modify: `src/teamster/code_locations/kipptaf/freshness.py:37-38`
- Test: `tests/test_automation_conditions.py` (`TestKipptafDbtAssets`)

**Interfaces:**

- Consumes: `with_failed_deps_guard` and the translator behavior from Task 1.

- [ ] **Step 1: Write the failing manifest test**

Add `test_adp_workers_staging_blocks_on_failed_deps(self, nodes_by_name)` to
`TestKipptafDbtAssets`, built like `test_gpa_snapshots_get_cron_condition`.

```python
props = nodes_by_name["stg_adp_workforce_now__workers"]
assert props["config"]["meta"]["dagster"]["group"] == "adp_workforce_now"
assert translator.get_automation_condition(props) == with_failed_deps_guard(
    dbt_table_automation_condition()
)
assert translator.get_asset_key(props) == AssetKey(
    ["kipptaf", "adp_workforce_now", "stg_adp_workforce_now__workers"]
)
```

- [ ] **Step 2: Build the manifest and run it to verify it fails**

Run:
`uv run dagster-dbt project prepare-and-package --file src/teamster/code_locations/kipptaf/__init__.py 2>&1 | tail -n 5`
then
`uv run pytest tests/test_automation_conditions.py -k test_adp_workers_staging_blocks_on_failed_deps -q 2>&1 | tail -n 15`
Expected: FAIL on the condition assertion; the group and asset-key assertions
already hold.

- [ ] **Step 3: Add the flag to the model YAML**

Under the model, after `description`, add
`config: {meta: {dagster: {automation_condition: {block_on_failed_deps: true}}}}`
in block style, with a one-line YAML comment saying why (staging must not build
over a failed ADP partition; it waits for the rerun). Read
`.claude/rules/dbt-yaml.md` (loads on the Read of this file) for placement.

- [ ] **Step 4: Rebuild the manifest and run the test**

Same two commands as Step 2. Expected: `1 passed`. If the group assertion fails,
dbt replaced the folder meta: stop and record a ruling, since the asset would
change group.

- [ ] **Step 5: Remove the roster freshness entries**

Delete the `int_people__staff_roster` and `int_people__staff_roster_history`
lines from `policies` in `src/teamster/code_locations/kipptaf/freshness.py`.
Leave `stg_people__employee_numbers` and staging. Check the import still loads:
`uv run python -c "import teamster.code_locations.kipptaf.freshness as f; print(len(f.policies))"`
Expected: two fewer entries than before the edit.

- [ ] **Step 6: Run the full suite slice**

Run: `uv run pytest tests/test_automation_conditions.py -q 2>&1 | tail -n 15`
Expected: all pass. Then lint the YAML and markdown:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <yml> src/teamster/core/CLAUDE.md src/teamster/libraries/dbt/CLAUDE.md docs/superpowers/plans/2026-11-03-adp-staging-failed-deps-guard.md </dev/null`
Expected: no issues.

- [ ] **Step 7: Commit**

```bash
git add -u
git commit -m "feat(dbt): hold ADP workers staging while a partition is failed"
```

## After merge (not a task)

- Confirm the kipptaf location reloaded on the merge commit
  (`get_location_load_history`).
- On the next night, the day-2 check confirms staging built once around
  00:45–00:55, and `get_asset_condition_evaluations` on staging shows the
  `any_deps_failed` node false.
