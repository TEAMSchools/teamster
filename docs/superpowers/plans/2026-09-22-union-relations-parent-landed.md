# union_relations parent-landed trigger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** kipptaf `union_relations` views rebuild on the tick a parent table's
post-code-change rebuild lands, instead of on the deploy tick.

**Architecture:** A new builder, `_build_parent_code_change_landed`, fires when
a parent's "pending code change" state turns off. The state is built from the
built-in `code_version_changed`, `since`, `newly_true`, and `newly_updated`
operands. It is wired into `_build_dbt_condition` through a new keyword argument
whose triggers reset only on `newly_requested`, and it replaces the deploy-tick
ancestor trigger in `dbt_union_relations_automation_condition`.

**Tech Stack:** Python 3.13, Dagster 1.13.24 declarative automation, pytest.

**Spec:**
`docs/superpowers/specs/2026-09-22-union-relations-parent-landed-design.md`
(issue #4290)

## Global Constraints

- Worktree:
  `/workspaces/teamster/.worktrees/cbini/fix/claude-union-relations-parent-landed`.
  Every path below is relative to it. Every git call is `git -C <worktree>`.
  Every Bash command starts with `cd <worktree> && pwd &&`.
- Always `uv run`, never bare `python`/`pytest`.
- Only built-in `AutomationCondition` operands and operators. No custom
  condition classes, and no `use_user_code_server`.
- View, table, and cron conditions must not change behavior. When
  `requested_reset_triggers` is `None`, `_build_dbt_condition` must build the
  same tree it builds today.
- Stage with `git add -u` (plus explicit paths for new files). Commit with
  `git commit -F <scratchpad>/commit-msg-<slug>.txt`, where the scratchpad is
  `/tmp/claude-1000/-workspaces-teamster/fb77f3fa-c96c-4a05-80a5-f5bcf31c7803/scratchpad`.
  End every message with
  `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Bound test output: `2>&1 | tail -n 30`.

## Review Focus

- **A plain data refresh after the trigger has fired:** it must not re-fire the
  wrapper. Pinned in Task 1 (the tail of
  `test_union_relations_view_waits_for_parent_code_change_to_land`).
- **Two parents that both change code (Newark and Camden in one deploy):** the
  wrapper must fire once per landing, because the second landing can change the
  column set again. Pinned in Task 1
  (`test_union_relations_view_fires_per_parent_landing`).
- **A trigger that arms while a gate holds the wrapper:** a stale wrapper
  materialization must not consume it. Pinned in Task 1
  (`test_union_relations_trigger_survives_stale_wrapper_run`).
- **The first evaluation after this change ships:** it must not request every
  wrapper. Pinned in Task 1
  (`test_union_relations_condition_change_does_not_fire_all`).
- **Sensor tick time on the real kipptaf graph:** the deeper tree must stay
  within `_SENSOR_BUDGET_SECONDS`. Pinned in Task 2.

---

### Task 1: Parent-landed trigger and its tests

**Files:**

- Modify: `src/teamster/core/automation_conditions.py` (`_build_dbt_condition`
  at lines 51-96, `dbt_union_relations_automation_condition` at lines 167-182,
  and a new builder after `_build_any_ancestor_code_version_changed` at
  line 153)
- Test: `tests/test_automation_conditions.py` (replace lines 1912-2002, the two
  `..._triggered_by_..._code_version_change` tests)

**Interfaces:**

- Produces:
  `_build_dbt_condition(*extra_triggers: AutomationCondition, requested_reset_triggers: AutomationCondition | None = None) -> AutomationCondition`
- Produces:
  `_build_parent_code_change_landed(max_depth: int = _MAX_VIEW_DEPTH, view_selection: AssetSelection | None = None) -> AutomationCondition`
- Unchanged signature:
  `dbt_union_relations_automation_condition() -> AutomationCondition`

- [ ] **Step 1: Put the kipptaf manifest in the worktree**

`TestKipptafDbtAssets` and the performance test read the kipptaf manifest, which
is gitignored and absent from a fresh worktree.

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-union-relations-parent-landed && pwd && mkdir -p src/dbt/kipptaf/target && cp /workspaces/teamster/src/dbt/kipptaf/target/manifest.json src/dbt/kipptaf/target/manifest.json && git status --short | head
```

Expected: `git status` shows nothing new (the target directory is ignored).

- [ ] **Step 2: Replace the two deploy-tick tests with the failing tests**

In `tests/test_automation_conditions.py`, delete
`test_union_relations_view_triggered_by_upstream_code_version_change` and
`test_union_relations_view_triggered_by_ancestor_code_version_change` (lines
1912-2002). In their place, insert:

```python
def _deploy(asset_name: str, code_version: str, tags: dict, deps=None):
    """Return a replacement asset simulating a deploy that bumps code_version."""

    @asset(key=asset_name, tags=tags, code_version=code_version, deps=deps)
    def _redeployed():
        return 1

    return _redeployed


def test_union_relations_view_waits_for_parent_code_change_to_land():
    """The wrapper must NOT rebuild on the deploy tick, when the parent table
    still has its old schema. It rebuilds on the tick the parent's
    post-deploy materialization lands, exactly once, and a later data-only
    refresh of the parent does not re-fire it (issue #4290: finalsite and
    amplify PM incidents).
    """

    @asset(tags=_TABLE_TAG, code_version="1")
    def regional_table():
        return 1

    @asset(
        deps=[regional_table],
        automation_condition=_get_union_relations_condition(),
        tags=_VIEW_TAG,
    )
    def union_relations_view():
        return 2

    instance = DagsterInstance.ephemeral()
    defs = Definitions(assets=[regional_table, union_relations_view])
    materialize(assets=[regional_table, union_relations_view], instance=instance)
    result = evaluate_automation_conditions(defs=defs, instance=instance)
    assert result.total_requested == 0

    regional_table_v2 = _deploy("regional_table", "2", _TABLE_TAG)
    defs_v2 = Definitions(assets=[regional_table_v2, union_relations_view])
    wrapper = AssetKey("union_relations_view")

    # Deploy tick: parent has the new code version but has not rebuilt
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(wrapper) == 0

    # Parent's post-deploy rebuild lands
    materialize(
        assets=[regional_table_v2, union_relations_view],
        instance=instance,
        selection=[regional_table_v2],
    )
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(wrapper) == 1

    # Trigger resets on the request
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(wrapper) == 0

    # Data-only refresh of the parent afterwards: no re-fire
    materialize(
        assets=[regional_table_v2, union_relations_view],
        instance=instance,
        selection=[regional_table_v2],
    )
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(wrapper) == 0


def test_union_relations_view_fires_when_table_behind_view_lands():
    """A table behind an intermediate view counts as a parent: the wrapper
    rebuilds when that table's post-deploy materialization lands, even though
    the intermediate view never rematerializes.

    Chain: staging_table (table) -> intermediate_view (view) -> wrapper.
    """

    @asset(tags=_TABLE_TAG, code_version="1")
    def staging_table():
        return 1

    @asset(
        deps=[staging_table],
        automation_condition=_get_view_condition(),
        tags=_VIEW_TAG,
    )
    def intermediate_view():
        return 2

    @asset(
        deps=[intermediate_view],
        automation_condition=_get_union_relations_condition(),
        tags=_VIEW_TAG,
    )
    def union_relations_view():
        return 3

    instance = DagsterInstance.ephemeral()
    all_assets = [staging_table, intermediate_view, union_relations_view]
    materialize(assets=all_assets, instance=instance)
    result = evaluate_automation_conditions(
        defs=Definitions(assets=all_assets), instance=instance
    )
    assert result.total_requested == 0

    staging_table_v2 = _deploy("staging_table", "2", _TABLE_TAG)
    assets_v2 = [staging_table_v2, intermediate_view, union_relations_view]
    defs_v2 = Definitions(assets=assets_v2)
    wrapper = AssetKey("union_relations_view")

    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(wrapper) == 0

    materialize(assets=assets_v2, instance=instance, selection=[staging_table_v2])
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(wrapper) == 1


def test_union_relations_view_fires_when_grandparent_change_reaches_parent():
    """Overgrad shape (issue #4290, second comment): the code change is two
    hops up, behind a parent table whose own code never changes. The wrapper
    must wait for the PARENT to rebuild, not just the changed grandparent.

    Chain: pivot (table, code change) -> admissions (table) -> wrapper.
    """

    @asset(tags=_TABLE_TAG, code_version="1")
    def pivot():
        return 1

    @asset(deps=[pivot], tags=_TABLE_TAG, code_version="1")
    def admissions():
        return 2

    @asset(
        deps=[admissions],
        automation_condition=_get_union_relations_condition(),
        tags=_VIEW_TAG,
    )
    def union_relations_view():
        return 3

    instance = DagsterInstance.ephemeral()
    all_assets = [pivot, admissions, union_relations_view]
    materialize(assets=all_assets, instance=instance)
    result = evaluate_automation_conditions(
        defs=Definitions(assets=all_assets), instance=instance
    )
    assert result.total_requested == 0

    pivot_v2 = _deploy("pivot", "2", _TABLE_TAG)
    assets_v2 = [pivot_v2, admissions, union_relations_view]
    defs_v2 = Definitions(assets=assets_v2)
    wrapper = AssetKey("union_relations_view")

    # Deploy tick
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(wrapper) == 0

    # Grandparent rebuilds; parent still carries the old schema
    materialize(assets=assets_v2, instance=instance, selection=[pivot_v2])
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(wrapper) == 0

    # Parent's data rebuild picks up the grandparent change
    materialize(assets=assets_v2, instance=instance, selection=[admissions])
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(wrapper) == 1


def test_union_relations_trigger_survives_stale_wrapper_run():
    """A wrapper materialization from a run that started before the parent
    landed (stale in-flight run, or a manual UI run) must not consume the
    trigger (issue #4290, overgrad mechanism).

    The ~any_deps_missing gate holds the wrapper back while
    other_regional_table is missing, which stands in for the
    ~any_deps_in_progress gate in prod.
    """

    @asset(tags=_TABLE_TAG, code_version="1")
    def regional_table():
        return 1

    @asset(tags=_TABLE_TAG)
    def other_regional_table():
        return 1

    @asset(
        deps=[regional_table, other_regional_table],
        automation_condition=_get_union_relations_condition(),
        tags=_VIEW_TAG,
    )
    def union_relations_view():
        return 2

    instance = DagsterInstance.ephemeral()
    all_assets = [regional_table, other_regional_table, union_relations_view]
    materialize(
        assets=all_assets,
        instance=instance,
        selection=[regional_table, union_relations_view],
    )
    result = evaluate_automation_conditions(
        defs=Definitions(assets=all_assets), instance=instance
    )
    assert result.total_requested == 0

    regional_table_v2 = _deploy("regional_table", "2", _TABLE_TAG)
    assets_v2 = [regional_table_v2, other_regional_table, union_relations_view]
    defs_v2 = Definitions(assets=assets_v2)
    wrapper = AssetKey("union_relations_view")

    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(wrapper) == 0

    # Parent lands while the gate holds the wrapper
    materialize(assets=assets_v2, instance=instance, selection=[regional_table_v2])
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(wrapper) == 0

    # Stale wrapper run finishes
    materialize(assets=assets_v2, instance=instance, selection=[union_relations_view])
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(wrapper) == 0

    # Gate opens: the trigger is still armed
    materialize(assets=assets_v2, instance=instance, selection=[other_regional_table])
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(wrapper) == 1


def test_union_relations_view_fires_per_parent_landing():
    """Two parents change code in one deploy (e.g. Newark and Camden). Each
    landing can change the column set, so the wrapper fires once per landing.
    """

    @asset(tags=_TABLE_TAG, code_version="1")
    def newark_table():
        return 1

    @asset(tags=_TABLE_TAG, code_version="1")
    def camden_table():
        return 1

    @asset(
        deps=[newark_table, camden_table],
        automation_condition=_get_union_relations_condition(),
        tags=_VIEW_TAG,
    )
    def union_relations_view():
        return 2

    instance = DagsterInstance.ephemeral()
    all_assets = [newark_table, camden_table, union_relations_view]
    materialize(assets=all_assets, instance=instance)
    result = evaluate_automation_conditions(
        defs=Definitions(assets=all_assets), instance=instance
    )
    assert result.total_requested == 0

    newark_v2 = _deploy("newark_table", "2", _TABLE_TAG)
    camden_v2 = _deploy("camden_table", "2", _TABLE_TAG)
    assets_v2 = [newark_v2, camden_v2, union_relations_view]
    defs_v2 = Definitions(assets=assets_v2)
    wrapper = AssetKey("union_relations_view")

    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(wrapper) == 0

    materialize(assets=assets_v2, instance=instance, selection=[newark_v2])
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(wrapper) == 1

    # Pretend the requested run completed
    materialize(assets=assets_v2, instance=instance, selection=[union_relations_view])
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(wrapper) == 0

    materialize(assets=assets_v2, instance=instance, selection=[camden_v2])
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(wrapper) == 1


def test_union_relations_condition_change_does_not_fire_all():
    """Shipping the new condition changes the condition tree, so its new nodes
    have no cursor. newly_true() treats a missing cursor as "everything newly
    true"; the first evaluation must still request nothing when no parent
    updated.
    """

    @asset(tags=_TABLE_TAG, code_version="1")
    def regional_table():
        return 1

    @asset(
        key="union_relations_view",
        deps=[regional_table],
        automation_condition=_get_view_condition(),
        tags=_VIEW_TAG,
    )
    def wrapper_old_condition():
        return 2

    @asset(
        key="union_relations_view",
        deps=[regional_table],
        automation_condition=_get_union_relations_condition(),
        tags=_VIEW_TAG,
    )
    def wrapper_new_condition():
        return 2

    instance = DagsterInstance.ephemeral()
    materialize(assets=[regional_table, wrapper_old_condition], instance=instance)
    result = evaluate_automation_conditions(
        defs=Definitions(assets=[regional_table, wrapper_old_condition]),
        instance=instance,
    )
    assert result.total_requested == 0

    result = evaluate_automation_conditions(
        defs=Definitions(assets=[regional_table, wrapper_new_condition]),
        instance=instance,
        cursor=result.cursor,
    )
    assert result.get_num_requested(AssetKey("union_relations_view")) == 0
```

- [ ] **Step 3: Run the new tests and confirm the expected failures**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-union-relations-parent-landed && pwd && uv run pytest tests/test_automation_conditions.py -k "union_relations" -q 2>&1 | tail -n 30
```

Expected under the current code:

- FAIL `test_union_relations_view_waits_for_parent_code_change_to_land`: the
  deploy-tick assert gets 1, not 0.
- FAIL `test_union_relations_view_fires_when_table_behind_view_lands`: the
  deploy-tick assert gets 1.
- FAIL `test_union_relations_view_fires_when_grandparent_change_reaches_parent`:
  the deploy-tick assert gets 1.
- FAIL `test_union_relations_trigger_survives_stale_wrapper_run`: the final
  assert gets 0.
- FAIL `test_union_relations_view_fires_per_parent_landing`: the deploy-tick
  assert gets 1.
- `test_union_relations_condition_change_does_not_fire_all` and
  `test_union_relations_view_not_triggered_by_upstream_data_update` may pass.
  They are regression guards.

If a test fails for a different reason (an error, not an assert), fix the test
before continuing.

- [ ] **Step 4: Add `requested_reset_triggers` to `_build_dbt_condition`**

In `src/teamster/core/automation_conditions.py`, replace the signature and the
body after the docstring of `_build_dbt_condition`:

```python
def _build_dbt_condition(
    *extra_triggers: AutomationCondition,
    requested_reset_triggers: AutomationCondition | None = None,
) -> AutomationCondition:
```

Append this paragraph to the end of its docstring, before the closing `"""`:

```text
    ``requested_reset_triggers`` stay armed until this asset is requested,
    not until it is updated. A materialization from a run that started
    before the trigger fired (a stale in-flight run, or a manual UI run)
    therefore cannot consume it.
```

Replace the body after the docstring with:

```python
    triggers: AutomationCondition = AutomationCondition.newly_missing()
    for trigger in extra_triggers:
        triggers = triggers | trigger

    handled = triggers.since(
        _SINCE_LAST_HANDLED
    ) | AutomationCondition.code_version_changed().since(
        AutomationCondition.newly_updated()
    )
    if requested_reset_triggers is not None:
        handled = handled | requested_reset_triggers.since(
            AutomationCondition.newly_requested()
        )

    return (
        AutomationCondition.in_latest_time_window()
        & handled
        & ~AutomationCondition.any_deps_missing().ignore(_EXTERNAL_SOURCE_SELECTION)
        & ~AutomationCondition.any_deps_in_progress()
        & ~AutomationCondition.in_progress()
    )
```

- [ ] **Step 5: Add `_build_parent_code_change_landed`**

Insert after `_build_any_ancestor_code_version_changed`:

```python
def _build_parent_code_change_landed(
    max_depth: int = _MAX_VIEW_DEPTH, view_selection: AssetSelection | None = None
) -> AutomationCondition:
    """Detect the tick a parent's post-code-change materialization lands.

    For each parent X, ``pending`` is true from the tick X or any of its
    ancestors changes code version until X next materializes. ``landed`` is
    true on the tick ``pending`` turns off, i.e. the tick X's rebuild lands.

    code_version_changed() alone cannot express this: it is true for exactly
    one tick (it compares against the previous tick's cursor), which is the
    deploy tick, before X has rebuilt.

    ``newly_true()`` is evaluated first so its child always sees the full
    subset. The ``newly_updated()`` conjunct keeps a cursor-less first
    evaluation (after a condition tree change) from firing for parents that
    did not update.

    Recursion follows view parents only (view_selection), so a table behind a
    view counts as a parent, mirroring _build_any_ancestor_updated.
    """
    pending = (
        AutomationCondition.code_version_changed()
        | _build_any_ancestor_code_version_changed(max_depth - 1)
    ).since(AutomationCondition.newly_updated())

    landed = (~pending).newly_true() & AutomationCondition.newly_updated()

    condition = AutomationCondition.any_deps_match(landed)

    for _ in range(max_depth - 1):
        recurse = AutomationCondition.any_deps_match(condition)

        if view_selection is not None:
            recurse = recurse.allow(view_selection)

        condition = AutomationCondition.any_deps_match(landed) | recurse

    return condition
```

- [ ] **Step 6: Switch `dbt_union_relations_automation_condition`**

Replace the whole function with:

```python
def dbt_union_relations_automation_condition() -> AutomationCondition:
    """Automation condition for dbt views using the union_relations macro.

    These views have compiled SQL that resolves column lists at run time.
    Because code_version is a SHA1 of raw_code (the Jinja source), not
    compiled SQL, the view's own code_version_changed won't fire when the
    macro output changes due to upstream schema changes.

    Behaves like a view, plus one trigger: rebuild on the tick a parent's
    post-code-change materialization lands (the parent's own code or any
    ancestor's), looking through view parents to the table behind them. It
    does NOT fire on the deploy tick, when the parent still has its old
    schema (issue #4290), and it does NOT fire on upstream data-only updates.

    Known limits:
    - A parent that reloads and finishes its rebuild within one sensor tick is
      missed: pending arms and resets on the same tick and the reset wins.
    - If a parent table does a data rebuild before its changed ancestor
      rebuilds, pending clears early and the view rebuilds against the old
      schema; the later rebuild does not re-fire it.
    - A phantom pending (stale cursor state) costs at most one extra view
      rebuild. It cannot deadlock: this is a trigger, not a gate.
    """
    return _build_dbt_condition(
        requested_reset_triggers=_build_parent_code_change_landed(
            view_selection=_VIEW_SELECTION
        )
    )
```

- [ ] **Step 7: Run the union_relations tests**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-union-relations-parent-landed && pwd && uv run pytest tests/test_automation_conditions.py -k "union_relations" -q 2>&1 | tail -n 30
```

Expected: all PASS, including
`test_union_relations_views_get_union_relations_condition` in
`TestKipptafDbtAssets`.

If `test_union_relations_trigger_survives_stale_wrapper_run` fails on the final
assert, check whether the `newly_requested` reset is in place (Step 4). If it
fails on an earlier assert, find the node that blocked it with `result.results`
and report back. Do not weaken the assert.

- [ ] **Step 8: Run the whole file to check nothing else moved**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-union-relations-parent-landed && pwd && uv run pytest tests/test_automation_conditions.py -q 2>&1 | tail -n 30
```

Expected: all PASS. Every view, table, and cron test must pass unchanged.

- [ ] **Step 9: Commit**

Write
`/tmp/claude-1000/-workspaces-teamster/fb77f3fa-c96c-4a05-80a5-f5bcf31c7803/scratchpad/commit-msg-task1.txt`:

```text
fix(dagster): rebuild union_relations views after parent code change lands

The deploy-tick ancestor code_version_changed trigger fired before the
district table rebuilt, so the wrapper compiled against the old column set
and nothing re-fired it. The new trigger fires on the tick a parent's
post-code-change materialization lands, and resets only on request so a
stale in-flight run cannot consume it.

Refs #4290

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
```

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-union-relations-parent-landed && pwd && git -C . add -u && git -C . commit -q -F /tmp/claude-1000/-workspaces-teamster/fb77f3fa-c96c-4a05-80a5-f5bcf31c7803/scratchpad/commit-msg-task1.txt && git -C . log --oneline -1
```

---

### Task 2: Sensor-budget check on the kipptaf graph

**Files:**

- Modify: `tests/test_automation_condition_performance.py` (module docstring
  lines 1-15 and the class docstring, which describe the old union_relations
  condition)

**Interfaces:**

- Consumes: `dbt_union_relations_automation_condition()` from Task 1.

- [ ] **Step 1: Record the baseline on the main checkout (old condition)**

Run in the background, because it can take minutes:

```bash
cd /workspaces/teamster && uv run pytest tests/test_automation_condition_performance.py -s -q > /tmp/claude-1000/-workspaces-teamster/fb77f3fa-c96c-4a05-80a5-f5bcf31c7803/scratchpad/perf-main.txt 2>&1
```

When it finishes, read the report table:
`rg -n "union_relations|Strategy|baseline|passed|failed" <scratchpad>/perf-main.txt`.
Note the `union_relations_only` warm time and the `union_relations` tree size.

- [ ] **Step 2: Run the same check on the worktree (new condition)**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-union-relations-parent-landed && uv run pytest tests/test_automation_condition_performance.py -s -q > /tmp/claude-1000/-workspaces-teamster/fb77f3fa-c96c-4a05-80a5-f5bcf31c7803/scratchpad/perf-branch.txt 2>&1
```

Expected: `test_current_strategy_within_sensor_budget` PASSES (warm is under
30s).

If it fails or times out: change the inner depth in
`_build_parent_code_change_landed` from `max_depth - 1` to `5`, re-run Task 1
Step 8, then re-run this step. If depth 5 is still over budget, stop and report
both timings. Do not raise `_SENSOR_BUDGET_SECONDS`.

- [ ] **Step 3: Update the stale performance-test docstrings**

In the module docstring, replace item 2:

```text
2. **Union-relations only** (current): Views with union_relations in raw_code
   get dbt_union_relations_automation_condition() (fires when a parent's
   post-code-change materialization lands); other views get the plain view
   condition.
```

In the `TestAutomationConditionPerformance` class docstring, replace the
`union_relations_only` bullet:

```text
    - union_relations_only: union_relations views get the parent-landed
      trigger (current state, issue #4290)
```

- [ ] **Step 4: Commit**

Write `<scratchpad>/commit-msg-task2.txt`:

```text
test(dagster): describe the parent-landed union_relations condition in perf docs

Refs #4290

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
```

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-union-relations-parent-landed && pwd && git -C . add -u && git -C . commit -q -F /tmp/claude-1000/-workspaces-teamster/fb77f3fa-c96c-4a05-80a5-f5bcf31c7803/scratchpad/commit-msg-task2.txt && git -C . log --oneline -1
```

Report both warm timings and both tree sizes (main vs branch) in the task
summary. They go into the PR body.

---

### Task 3: Published docs

**Files:**

- Modify: `docs/reference/automation-conditions.md` (the
  `### dbt_union_relations_automation_condition()` section, lines 50-66)

- [ ] **Step 1: Replace the section body**

Replace everything from the line after
`` ### `dbt_union_relations_automation_condition()` `` up to (not including) the
paragraph starting "The `CustomDagsterDbtTranslator` **auto-detects**" with:

```markdown
A third condition that sits between view and table. Triggers on everything in
the view condition, plus one extra trigger:

- **A parent's code change lands** — the view re-runs on the tick a parent
  table's post-code-change materialization lands. "Code change" covers the
  parent's own raw SQL or any of its ancestors'. View parents are looked through
  to the table behind them (up to 10 levels).

It does **not** re-run on the deploy tick itself. At that point the parent still
has its old schema, and re-running then compiles the stale column list
([#4290](https://github.com/TEAMSchools/teamster/issues/4290)). The trigger
stays armed until the view is requested, so a run that started before the parent
landed cannot consume it.

Unlike the table condition, this does **not** trigger on upstream data changes
(`any_deps_updated`). Re-materializing views on every upstream data refresh
would waste Dagster credits and Kubernetes resources.

Known limits: a parent that reloads and finishes rebuilding within one sensor
tick is missed; and if a parent table does a data rebuild before its changed
ancestor rebuilds, the view re-runs early against the old schema. In either
case, rematerialize the view from the Dagster UI.
```

- [ ] **Step 2: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-union-relations-parent-landed && pwd && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix docs/reference/automation-conditions.md docs/superpowers/plans/2026-09-22-union-relations-parent-landed.md </dev/null 2>&1 | tail -n 20
```

Expected: `No issues`. If prettier reports formatting, run
`/workspaces/teamster/.trunk/tools/trunk fmt <file> </dev/null` on that file and
re-check.

- [ ] **Step 3: Commit**

Write `<scratchpad>/commit-msg-task3.txt`:

```text
docs(dagster): describe the parent-landed union_relations trigger

Refs #4290

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
```

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-union-relations-parent-landed && pwd && git -C . add -u && git -C . commit -q -F /tmp/claude-1000/-workspaces-teamster/fb77f3fa-c96c-4a05-80a5-f5bcf31c7803/scratchpad/commit-msg-task3.txt && git -C . log --oneline -1
```
