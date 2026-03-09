import pytest
from dagster import (
    AssetKey,
    AssetSelection,
    AutomationCondition,
    DagsterInstance,
    Definitions,
    asset,
    evaluate_automation_conditions,
    materialize,
)

from teamster.core.automation_conditions import (
    dbt_table_automation_condition,
    dbt_view_automation_condition,
)

_EMPTY_SELECTION = AssetSelection.assets()
_VIEW_TAG = {"dagster/materialized": "view"}
_TABLE_TAG = {"dagster/materialized": "table"}


def _get_view_condition() -> AutomationCondition:
    return dbt_view_automation_condition(ignore_selection=_EMPTY_SELECTION)


def _get_table_condition() -> AutomationCondition:
    return dbt_table_automation_condition(ignore_selection=_EMPTY_SELECTION)


def test_view_not_requested_on_upstream_update():
    """Views should NOT be requested when an upstream table is updated."""

    @asset(tags=_TABLE_TAG)
    def upstream_table():
        return 1

    @asset(
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        tags=_VIEW_TAG,
    )
    def my_view():
        return 2

    instance = DagsterInstance.ephemeral()
    all_assets = [upstream_table, my_view]
    defs = Definitions(assets=all_assets)

    materialize(assets=all_assets, instance=instance)

    result = evaluate_automation_conditions(defs=defs, instance=instance)
    assert result.total_requested == 0

    materialize(assets=[upstream_table], instance=instance, selection=[upstream_table])

    result = evaluate_automation_conditions(
        defs=defs, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("my_view")) == 0


def test_table_requested_on_upstream_update():
    """Tables SHOULD be requested when a direct upstream table is updated."""

    @asset(tags=_TABLE_TAG)
    def upstream_table():
        return 1

    @asset(
        deps=[upstream_table],
        automation_condition=_get_table_condition(),
        tags=_TABLE_TAG,
    )
    def downstream_table():
        return 2

    instance = DagsterInstance.ephemeral()
    all_assets = [upstream_table, downstream_table]
    defs = Definitions(assets=all_assets)

    materialize(assets=all_assets, instance=instance)
    result = evaluate_automation_conditions(defs=defs, instance=instance)

    materialize(assets=[upstream_table], instance=instance, selection=[upstream_table])

    result = evaluate_automation_conditions(
        defs=defs, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("downstream_table")) == 1


def test_table_code_version_change_without_intermediate_materialization():
    """Tables should detect code_version_changed even when the table was
    requested but never actually materialized between version changes.

    Same bug as the view variant: .since(newly_requested) resets the gate
    when the table is requested, and if materialization never happens before
    the next code version change, the event is lost.
    """

    @asset(tags=_TABLE_TAG)
    def upstream_table():
        return 1

    @asset(
        key="my_table",
        deps=[upstream_table],
        automation_condition=_get_table_condition(),
        code_version="1",
        tags=_TABLE_TAG,
    )
    def my_table_v1():
        return 2

    instance = DagsterInstance.ephemeral()
    all_assets = [upstream_table, my_table_v1]
    defs = Definitions(assets=all_assets)

    # Initial materialization
    materialize(assets=all_assets, instance=instance)
    result = evaluate_automation_conditions(defs=defs, instance=instance)
    assert result.get_num_requested(AssetKey("my_table")) == 0

    # Code version changes to "2", table is requested
    @asset(
        key="my_table",
        deps=[upstream_table],
        automation_condition=_get_table_condition(),
        code_version="2",
        tags=_TABLE_TAG,
    )
    def my_table_v2():
        return 2

    defs_v2 = Definitions(assets=[upstream_table, my_table_v2])
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("my_table")) == 1

    # Table is NOT materialized; code version changes to "3"
    @asset(
        key="my_table",
        deps=[upstream_table],
        automation_condition=_get_table_condition(),
        code_version="3",
        tags=_TABLE_TAG,
    )
    def my_table_v3():
        return 2

    defs_v3 = Definitions(assets=[upstream_table, my_table_v3])
    result = evaluate_automation_conditions(
        defs=defs_v3, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("my_table")) == 1


def test_table_not_blocked_by_external_source_asset():
    """Tables should NOT be blocked by unmaterialized external source assets."""
    from dagster import AssetSpec, SourceAsset

    external_source = SourceAsset(key="external_feed")

    @asset(
        deps=[AssetSpec("external_feed")],
        automation_condition=_get_table_condition(),
        code_version="1",
        tags=_TABLE_TAG,
    )
    def my_table():
        return 1

    instance = DagsterInstance.ephemeral()
    defs = Definitions(assets=[external_source, my_table])

    # Table is newly_missing, should be requested despite external source
    # never having been materialized or observed
    result = evaluate_automation_conditions(defs=defs, instance=instance)
    assert result.get_num_requested(AssetKey("my_table")) == 1


def test_table_view_table_chain():
    """Core test: Table -> View -> Table chain.

    When upstream_table is materialized:
    - intermediate_view should NOT be requested (it's a view)
    - downstream_table SHOULD be requested (sees through the view)
    """

    @asset(tags=_TABLE_TAG)
    def upstream_table():
        return 1

    @asset(
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        tags=_VIEW_TAG,
    )
    def intermediate_view():
        return 2

    @asset(
        deps=[intermediate_view],
        automation_condition=_get_table_condition(),
        tags=_TABLE_TAG,
    )
    def downstream_table():
        return 3

    instance = DagsterInstance.ephemeral()
    all_assets = [upstream_table, intermediate_view, downstream_table]
    defs = Definitions(assets=all_assets)

    materialize(assets=all_assets, instance=instance)
    result = evaluate_automation_conditions(defs=defs, instance=instance)
    assert result.total_requested == 0

    materialize(assets=[upstream_table], instance=instance, selection=[upstream_table])

    result = evaluate_automation_conditions(
        defs=defs, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("intermediate_view")) == 0
    assert result.get_num_requested(AssetKey("downstream_table")) == 1


def test_double_view_chain():
    """Table -> View -> View -> Table chain.

    Tests that the ancestor lookthrough handles multiple consecutive views.
    """

    @asset(tags=_TABLE_TAG)
    def source_table():
        return 1

    @asset(
        deps=[source_table], automation_condition=_get_view_condition(), tags=_VIEW_TAG
    )
    def view_a():
        return 2

    @asset(deps=[view_a], automation_condition=_get_view_condition(), tags=_VIEW_TAG)
    def view_b():
        return 3

    @asset(deps=[view_b], automation_condition=_get_table_condition(), tags=_TABLE_TAG)
    def target_table():
        return 4

    instance = DagsterInstance.ephemeral()
    all_assets = [source_table, view_a, view_b, target_table]
    defs = Definitions(assets=all_assets)

    materialize(assets=all_assets, instance=instance)
    result = evaluate_automation_conditions(defs=defs, instance=instance)

    materialize(assets=[source_table], instance=instance, selection=[source_table])
    result = evaluate_automation_conditions(
        defs=defs, instance=instance, cursor=result.cursor
    )

    assert result.get_num_requested(AssetKey("view_a")) == 0
    assert result.get_num_requested(AssetKey("view_b")) == 0
    assert result.get_num_requested(AssetKey("target_table")) == 1


def test_update_propagates_through_view_between_tables():
    """Table -> Table -> View -> Table chain.

    When source_table is updated:
    - middle_table sees the direct dep update and is requested
    - will_be_requested() makes middle_table visible to intervening_view's deps
    - downstream_table's ancestor lookthrough sees middle_table through the view
    - All tables in the chain are correctly requested
    """

    @asset(tags=_TABLE_TAG)
    def source_table():
        return 1

    @asset(
        deps=[source_table],
        automation_condition=_get_table_condition(),
        tags=_TABLE_TAG,
    )
    def middle_table():
        return 2

    @asset(
        deps=[middle_table],
        automation_condition=_get_view_condition(),
        tags=_VIEW_TAG,
    )
    def intervening_view():
        return 3

    @asset(
        deps=[intervening_view],
        automation_condition=_get_table_condition(),
        tags=_TABLE_TAG,
    )
    def downstream_table():
        return 4

    instance = DagsterInstance.ephemeral()
    all_assets = [source_table, middle_table, intervening_view, downstream_table]
    defs = Definitions(assets=all_assets)

    materialize(assets=all_assets, instance=instance)
    result = evaluate_automation_conditions(defs=defs, instance=instance)
    assert result.total_requested == 0

    # Update only source_table
    materialize(assets=[source_table], instance=instance, selection=[source_table])

    result = evaluate_automation_conditions(
        defs=defs, instance=instance, cursor=result.cursor
    )

    # middle_table should be requested (direct dep updated)
    assert result.get_num_requested(AssetKey("middle_table")) == 1
    # intervening_view should NOT be requested (view ignores upstream updates)
    assert result.get_num_requested(AssetKey("intervening_view")) == 0
    # downstream_table SHOULD be requested — ancestor lookthrough sees
    # middle_table (will_be_requested) through intervening_view
    assert result.get_num_requested(AssetKey("downstream_table")) == 1


def test_view_requested_on_execution_failure():
    """Views SHOULD be requested when their last execution failed."""

    @asset(tags=_TABLE_TAG)
    def upstream_table():
        return 1

    @asset(
        key="my_view",
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        tags=_VIEW_TAG,
    )
    def my_view_ok():
        return 2

    instance = DagsterInstance.ephemeral()
    all_assets = [upstream_table, my_view_ok]
    defs = Definitions(assets=all_assets)

    # Initial materialization succeeds
    materialize(assets=all_assets, instance=instance)
    result = evaluate_automation_conditions(defs=defs, instance=instance)
    assert result.get_num_requested(AssetKey("my_view")) == 0

    # Redefine the view to raise an error
    @asset(
        key="my_view",
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        tags=_VIEW_TAG,
    )
    def my_view_fails():
        raise Exception("intentional failure")

    defs_fail = Definitions(assets=[upstream_table, my_view_fails])
    materialize(
        assets=[my_view_fails],
        instance=instance,
        selection=[my_view_fails],
        raise_on_error=False,
    )

    result = evaluate_automation_conditions(
        defs=defs_fail, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("my_view")) == 1


def test_view_requested_on_code_version_change():
    """Views SHOULD be requested when their code version changes."""

    @asset(tags=_TABLE_TAG)
    def upstream_table():
        return 1

    @asset(
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        code_version="1",
        tags=_VIEW_TAG,
    )
    def my_view():
        return 2

    instance = DagsterInstance.ephemeral()
    all_assets = [upstream_table, my_view]
    defs = Definitions(assets=all_assets)

    materialize(assets=all_assets, instance=instance)
    result = evaluate_automation_conditions(defs=defs, instance=instance)
    assert result.get_num_requested(AssetKey("my_view")) == 0

    # Simulate code version change by redefining with new version
    @asset(
        key="my_view",
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        code_version="2",
        tags=_VIEW_TAG,
    )
    def my_view_v2():
        return 2

    defs_v2 = Definitions(assets=[upstream_table, my_view_v2])
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("my_view")) == 1


def test_view_not_blocked_by_external_source_asset():
    """Views should NOT be blocked by unmaterialized external source assets.

    Without .ignore(_EXTERNAL_SOURCE_SELECTION) on the any_deps_missing guard,
    an external source asset (SourceAsset) that has never been materialized or
    observed would cause any_deps_missing() to be true, permanently blocking
    downstream automation.

    This test verifies the ignore is still necessary by testing both:
    - The current condition (with ignore) works correctly
    - eager() (without ignore) would block the view
    """
    from dagster import AssetSpec, SourceAsset

    external_source = SourceAsset(key="external_feed")

    @asset(
        deps=[AssetSpec("external_feed")],
        automation_condition=_get_view_condition(),
        code_version="1",
        tags=_VIEW_TAG,
    )
    def my_view():
        return 1

    instance = DagsterInstance.ephemeral()
    defs = Definitions(assets=[external_source, my_view])

    # Initial: view is newly_missing, should be requested despite
    # external_feed never having been materialized or observed
    result = evaluate_automation_conditions(defs=defs, instance=instance)
    assert result.get_num_requested(AssetKey("my_view")) == 1


def test_view_blocked_by_external_source_without_ignore():
    """Confirms that eager() (no source ignore) WOULD block on external sources.

    This is the counter-test: using AutomationCondition.eager() which has
    unfiltered any_deps_missing(), the view should be blocked when the
    external source has no materialization/observation records.
    """
    from dagster import AssetSpec, SourceAsset

    external_source = SourceAsset(key="external_feed")

    @asset(
        deps=[AssetSpec("external_feed")],
        automation_condition=AutomationCondition.eager(),
        tags=_VIEW_TAG,
    )
    def my_view():
        return 1

    instance = DagsterInstance.ephemeral()
    defs = Definitions(assets=[external_source, my_view])

    # eager() has unfiltered any_deps_missing — external source blocks the view
    result = evaluate_automation_conditions(defs=defs, instance=instance)
    assert result.get_num_requested(AssetKey("my_view")) == 0


def test_view_code_version_change_after_failed_materialization():
    """Views should still detect code_version_changed after a failed materialization.

    Scenario:
    1. View materialized with code_version="1" — success
    2. View is re-run and FAILS
    3. execution_failed triggers re-request, succeeds
    4. Code version changes to "2"
    5. code_version_changed should detect this and request the view

    This tests whether the .since() reset from the recovery materialization
    (newly_updated) properly allows code_version_changed to fire on the
    next evaluation.
    """

    @asset(tags=_TABLE_TAG)
    def upstream_table():
        return 1

    @asset(
        key="my_view",
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        code_version="1",
        tags=_VIEW_TAG,
    )
    def my_view_v1():
        return 2

    instance = DagsterInstance.ephemeral()
    all_assets = [upstream_table, my_view_v1]
    defs = Definitions(assets=all_assets)

    # Step 1: Initial materialization succeeds
    materialize(assets=all_assets, instance=instance)
    result = evaluate_automation_conditions(defs=defs, instance=instance)
    assert result.get_num_requested(AssetKey("my_view")) == 0

    # Step 2: View execution fails
    @asset(
        key="my_view",
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        code_version="1",
        tags=_VIEW_TAG,
    )
    def my_view_fails():
        raise Exception("intentional failure")

    defs_fail = Definitions(assets=[upstream_table, my_view_fails])
    materialize(
        assets=[my_view_fails],
        instance=instance,
        selection=[my_view_fails],
        raise_on_error=False,
    )

    # Step 3: execution_failed should trigger re-request
    result = evaluate_automation_conditions(
        defs=defs_fail, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("my_view")) == 1

    # Simulate recovery: re-materialize successfully with code_version="1"
    materialize(assets=[my_view_v1], instance=instance, selection=[my_view_v1])
    result = evaluate_automation_conditions(
        defs=defs, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("my_view")) == 0

    # Step 4-5: Code version changes to "2" — should be requested
    @asset(
        key="my_view",
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        code_version="2",
        tags=_VIEW_TAG,
    )
    def my_view_v2():
        return 2

    defs_v2 = Definitions(assets=[upstream_table, my_view_v2])
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("my_view")) == 1


def test_view_code_version_change_without_intermediate_materialization():
    """Views should detect code_version_changed even when the view was
    requested but never actually materialized between version changes.

    Scenario:
    1. View materialized with code_version="1" — success
    2. Code version changes to "2"
    3. Evaluation: view is requested (code_version_changed fires)
    4. View is NOT materialized (request was made but mat didn't happen)
    5. Code version changes to "3"
    6. Evaluation: view should still be requested

    This tests whether newly_requested resetting .since() prevents
    code_version_changed from firing on subsequent evaluations when the
    view was never actually materialized with the new code.
    """

    @asset(tags=_TABLE_TAG)
    def upstream_table():
        return 1

    @asset(
        key="my_view",
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        code_version="1",
        tags=_VIEW_TAG,
    )
    def my_view_v1():
        return 2

    instance = DagsterInstance.ephemeral()
    all_assets = [upstream_table, my_view_v1]
    defs = Definitions(assets=all_assets)

    # Step 1: Initial materialization
    materialize(assets=all_assets, instance=instance)
    result = evaluate_automation_conditions(defs=defs, instance=instance)
    assert result.get_num_requested(AssetKey("my_view")) == 0

    # Step 2-3: Code version changes to "2", view is requested
    @asset(
        key="my_view",
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        code_version="2",
        tags=_VIEW_TAG,
    )
    def my_view_v2():
        return 2

    defs_v2 = Definitions(assets=[upstream_table, my_view_v2])
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("my_view")) == 1

    # Step 4: View is NOT materialized (simulating request without execution)
    # Step 5-6: Code version changes to "3", should still be requested
    @asset(
        key="my_view",
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        code_version="3",
        tags=_VIEW_TAG,
    )
    def my_view_v3():
        return 2

    defs_v3 = Definitions(assets=[upstream_table, my_view_v3])
    result = evaluate_automation_conditions(
        defs=defs_v3, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("my_view")) == 1


def test_view_code_version_change_detected_after_second_materialization():
    """Views should detect code_version_changed across multiple
    materialize-then-change cycles.

    Scenario:
    1. View materialized with code_version="1"
    2. Code changes to "2" → requested and materialized
    3. Code changes to "3" → should be requested again

    This ensures the .since() properly resets and re-fires across
    consecutive code version changes that are each followed by
    successful materializations.
    """

    @asset(tags=_TABLE_TAG)
    def upstream_table():
        return 1

    @asset(
        key="my_view",
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        code_version="1",
        tags=_VIEW_TAG,
    )
    def my_view_v1():
        return 2

    instance = DagsterInstance.ephemeral()
    all_assets = [upstream_table, my_view_v1]
    defs_v1 = Definitions(assets=all_assets)

    # Cycle 1: materialize v1
    materialize(assets=all_assets, instance=instance)
    result = evaluate_automation_conditions(defs=defs_v1, instance=instance)
    assert result.get_num_requested(AssetKey("my_view")) == 0

    # Cycle 2: change to v2, request and materialize
    @asset(
        key="my_view",
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        code_version="2",
        tags=_VIEW_TAG,
    )
    def my_view_v2():
        return 2

    defs_v2 = Definitions(assets=[upstream_table, my_view_v2])
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("my_view")) == 1

    # Materialize with v2
    materialize(assets=[my_view_v2], instance=instance, selection=[my_view_v2])
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("my_view")) == 0

    # Cycle 3: change to v3 — should be requested
    @asset(
        key="my_view",
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        code_version="3",
        tags=_VIEW_TAG,
    )
    def my_view_v3():
        return 2

    defs_v3 = Definitions(assets=[upstream_table, my_view_v3])
    result = evaluate_automation_conditions(
        defs=defs_v3, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("my_view")) == 1


def test_view_code_version_change_blocked_by_missing_deps_then_unblocked():
    """code_version_changed should fire once deps become available, even if
    the code version changed while deps were missing.

    Scenario:
    1. View materialized with code_version="1" (upstream present)
    2. New upstream dep is added (missing — never materialized)
    3. Code version changes to "2"
    4. Evaluation: code_version_changed is true BUT any_deps_missing blocks
    5. Missing dep is materialized
    6. Evaluation: code_version_changed should still be detected

    This tests whether the .since() mechanism preserves the
    code_version_changed state across ticks where the request was blocked
    by an external guard (any_deps_missing).
    """

    @asset(tags=_TABLE_TAG)
    def upstream_a():
        return 1

    @asset(
        key="my_view",
        deps=[upstream_a],
        automation_condition=_get_view_condition(),
        code_version="1",
        tags=_VIEW_TAG,
    )
    def my_view_v1():
        return 2

    instance = DagsterInstance.ephemeral()
    defs = Definitions(assets=[upstream_a, my_view_v1])

    # Step 1: Materialize everything
    materialize(assets=[upstream_a, my_view_v1], instance=instance)
    result = evaluate_automation_conditions(defs=defs, instance=instance)
    assert result.get_num_requested(AssetKey("my_view")) == 0

    # Step 2-3: Add a new upstream dep and change code version
    @asset(tags=_TABLE_TAG)
    def upstream_b():
        return 10

    @asset(
        key="my_view",
        deps=[upstream_a, upstream_b],
        automation_condition=_get_view_condition(),
        code_version="2",
        tags=_VIEW_TAG,
    )
    def my_view_v2():
        return 2

    defs_v2 = Definitions(assets=[upstream_a, upstream_b, my_view_v2])

    # Step 4: upstream_b is missing → should block the request
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("my_view")) == 0

    # Step 5: Materialize the missing dep
    materialize(assets=[upstream_b], instance=instance, selection=[upstream_b])

    # Step 6: Now code_version_changed should fire
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("my_view")) == 1


class TestKipptafDbtAssets:
    """Integration tests using the real kipptaf dbt manifest.

    Validates that the CustomDagsterDbtTranslator correctly tags assets
    with dagster/materialized and that automation conditions are assigned
    based on the actual dbt project structure.
    """

    @pytest.fixture(scope="class")
    def all_dbt_assets(self):
        from teamster.code_locations.kipptaf.dbt.assets import all_dbt_assets

        return all_dbt_assets

    @pytest.fixture(scope="class")
    def specs_by_key(self, all_dbt_assets):
        return {s.key: s for s in all_dbt_assets.specs}

    @pytest.fixture(scope="class")
    def view_specs(self, all_dbt_assets):
        return [
            s
            for s in all_dbt_assets.specs
            if s.tags.get("dagster/materialized") == "view"
        ]

    @pytest.fixture(scope="class")
    def table_specs(self, all_dbt_assets):
        return [
            s
            for s in all_dbt_assets.specs
            if s.tags.get("dagster/materialized") == "table"
        ]

    def test_all_models_tagged_with_materialized(self, all_dbt_assets):
        """Every dbt model spec should have a dagster/materialized tag."""
        for spec in all_dbt_assets.specs:
            assert "dagster/materialized" in spec.tags, (
                f"{spec.key} missing dagster/materialized tag"
            )

    def test_materialized_tag_values(self, view_specs, table_specs, all_dbt_assets):
        """The materialized tag should only contain known dbt materialization values."""
        all_values = {s.tags["dagster/materialized"] for s in all_dbt_assets.specs}
        known = {"view", "table", "incremental", "ephemeral", "seed", "snapshot"}
        assert all_values <= known, (
            f"Unexpected materialized values: {all_values - known}"
        )
        assert len(view_specs) > 0, "Expected at least one view model"
        assert len(table_specs) > 0, "Expected at least one table model"

    def test_most_views_have_automation_condition(self, view_specs):
        """Most view models should have an automation condition assigned.

        Some may be explicitly disabled via dbt meta (enabled: false).
        """
        with_condition = [s for s in view_specs if s.automation_condition is not None]
        without_condition = [s for s in view_specs if s.automation_condition is None]

        assert len(with_condition) > len(without_condition), (
            f"Most views should have conditions: "
            f"{len(with_condition)} with vs {len(without_condition)} without"
        )

    def test_most_tables_have_automation_condition(self, table_specs):
        """Most table models should have an automation condition assigned.

        Some may be explicitly disabled via dbt meta (enabled: false).
        """
        with_condition = [s for s in table_specs if s.automation_condition is not None]
        without_condition = [s for s in table_specs if s.automation_condition is None]

        assert len(with_condition) > len(without_condition), (
            f"Most tables should have conditions: "
            f"{len(with_condition)} with vs {len(without_condition)} without"
        )

    def test_view_selection_matches_view_tagged_specs(
        self, all_dbt_assets, view_specs, table_specs
    ):
        """The dagster/materialized tag should cleanly separate views from tables.

        Validates that _VIEW_SELECTION (tag-based) would correctly partition
        the asset graph by checking that no spec is tagged as both.
        """
        view_keys = {s.key for s in view_specs}
        table_keys = {s.key for s in table_specs}

        assert view_keys.isdisjoint(table_keys), (
            "No asset should be tagged as both view and table"
        )

        all_keys = {s.key for s in all_dbt_assets.specs}
        tagged_keys = view_keys | table_keys
        untagged = {
            s.key
            for s in all_dbt_assets.specs
            if s.tags.get("dagster/materialized") not in ("view", "table")
        }

        assert len(tagged_keys) > len(untagged), (
            f"Most assets should be tagged view or table: "
            f"{len(tagged_keys)} tagged vs {len(untagged)} other"
        )

        assert tagged_keys | untagged == all_keys

    def test_table_view_table_chain_exists_in_kipptaf(
        self, all_dbt_assets, specs_by_key
    ):
        """Find and validate a real table→view→table chain in kipptaf.

        Searches the asset graph for a table whose dep is a view whose dep
        is another table, then verifies all three have the expected tags.
        """
        chain_found = False

        for spec in all_dbt_assets.specs:
            if spec.tags.get("dagster/materialized") != "table":
                continue

            for dep in spec.deps:
                view_spec = specs_by_key.get(dep.asset_key)
                if (
                    view_spec is None
                    or view_spec.tags.get("dagster/materialized") != "view"
                ):
                    continue

                for grandparent_dep in view_spec.deps:
                    gp_spec = specs_by_key.get(grandparent_dep.asset_key)
                    if (
                        gp_spec is not None
                        and gp_spec.tags.get("dagster/materialized") == "table"
                    ):
                        chain_found = True

                        assert gp_spec.tags["dagster/materialized"] == "table"
                        assert view_spec.tags["dagster/materialized"] == "view"
                        assert spec.tags["dagster/materialized"] == "table"

                        assert gp_spec.automation_condition is not None
                        assert view_spec.automation_condition is not None
                        assert spec.automation_condition is not None
                        break

                if chain_found:
                    break
            if chain_found:
                break

        assert chain_found, "No table→view→table chain found in kipptaf dbt assets"


class TestKipptafChainTopologies:
    """Integration tests using real kipptaf dbt model topologies.

    Each test mirrors a real dependency chain found in the kipptaf manifest,
    using stub @asset functions with matching keys, tags, and conditions
    derived from the CustomDagsterDbtTranslator.
    """

    @pytest.fixture(scope="class")
    def manifest(self):
        import json

        from teamster.code_locations.kipptaf import DBT_PROJECT

        return json.loads(DBT_PROJECT.manifest_path.read_text())

    @pytest.fixture(scope="class")
    def translator(self):
        from teamster.libraries.dbt.dagster_dbt_translator import (
            CustomDagsterDbtTranslator,
        )

        return CustomDagsterDbtTranslator(code_location="kipptaf")

    @pytest.fixture(scope="class")
    def nodes_by_name(self, manifest):
        return {props["name"]: props for props in manifest["nodes"].values()}

    def _get_node(self, nodes_by_name: dict, name: str) -> dict:
        if name not in nodes_by_name:
            pytest.skip(
                f"Model '{name}' not found in kipptaf manifest (may have been renamed or removed)"
            )
        return nodes_by_name[name]

    def test_kipptaf_view_not_requested_on_upstream_update(
        self, translator, nodes_by_name
    ):
        """Real topology: stg_smartrecruiters__applications (table) →
        rpt_tableau__smartrecruiters (view).

        View should NOT be requested when the upstream table is updated.
        """
        upstream_props = self._get_node(
            nodes_by_name, "stg_smartrecruiters__applications"
        )
        view_props = self._get_node(nodes_by_name, "rpt_tableau__smartrecruiters")

        @asset(
            key=["kipptaf", "stg_smartrecruiters__applications"],
            tags=translator.get_tags(upstream_props),
        )
        def stg_smartrecruiters__applications():
            return 1

        @asset(
            key=["kipptaf", "rpt_tableau__smartrecruiters"],
            deps=[stg_smartrecruiters__applications],
            automation_condition=translator.get_automation_condition(view_props),
            tags=translator.get_tags(view_props),
        )
        def rpt_tableau__smartrecruiters():
            return 2

        instance = DagsterInstance.ephemeral()
        all_assets = [stg_smartrecruiters__applications, rpt_tableau__smartrecruiters]
        defs = Definitions(assets=all_assets)

        materialize(assets=all_assets, instance=instance)
        result = evaluate_automation_conditions(defs=defs, instance=instance)
        assert result.total_requested == 0

        materialize(
            assets=[stg_smartrecruiters__applications],
            instance=instance,
            selection=[stg_smartrecruiters__applications],
        )
        result = evaluate_automation_conditions(
            defs=defs, instance=instance, cursor=result.cursor
        )
        assert (
            result.get_num_requested(
                AssetKey(["kipptaf", "rpt_tableau__smartrecruiters"])
            )
            == 0
        )

    def test_kipptaf_table_requested_on_upstream_update(
        self, translator, nodes_by_name
    ):
        """Real topology: stg_renlearn__star (table) →
        int_topline__star_assessment_weekly (table).

        Downstream table should be requested when upstream table is updated.
        """
        upstream_props = self._get_node(nodes_by_name, "stg_renlearn__star")
        downstream_props = self._get_node(
            nodes_by_name, "int_topline__star_assessment_weekly"
        )

        @asset(
            key=["kipptaf", "stg_renlearn__star"],
            tags=translator.get_tags(upstream_props),
        )
        def stg_renlearn__star():
            return 1

        @asset(
            key=["kipptaf", "int_topline__star_assessment_weekly"],
            deps=[stg_renlearn__star],
            automation_condition=translator.get_automation_condition(downstream_props),
            tags=translator.get_tags(downstream_props),
        )
        def int_topline__star_assessment_weekly():
            return 2

        instance = DagsterInstance.ephemeral()
        all_assets = [stg_renlearn__star, int_topline__star_assessment_weekly]
        defs = Definitions(assets=all_assets)

        materialize(assets=all_assets, instance=instance)
        result = evaluate_automation_conditions(defs=defs, instance=instance)

        materialize(
            assets=[stg_renlearn__star],
            instance=instance,
            selection=[stg_renlearn__star],
        )
        result = evaluate_automation_conditions(
            defs=defs, instance=instance, cursor=result.cursor
        )
        assert (
            result.get_num_requested(
                AssetKey(["kipptaf", "int_topline__star_assessment_weekly"])
            )
            == 1
        )

    def test_kipptaf_table_view_table_chain(self, translator, nodes_by_name):
        """Real topology: int_extracts__student_enrollments_subjects (table) →
        int_extracts__student_enrollments_subjects_weeks (view) →
        int_topline__star_assessment_weekly (table).

        View should NOT be requested; downstream table SHOULD be requested.
        """
        source_props = self._get_node(
            nodes_by_name, "int_extracts__student_enrollments_subjects"
        )
        view_props = self._get_node(
            nodes_by_name, "int_extracts__student_enrollments_subjects_weeks"
        )
        target_props = self._get_node(
            nodes_by_name, "int_topline__star_assessment_weekly"
        )

        @asset(
            key=["kipptaf", "int_extracts__student_enrollments_subjects"],
            tags=translator.get_tags(source_props),
        )
        def int_extracts__student_enrollments_subjects():
            return 1

        @asset(
            key=["kipptaf", "int_extracts__student_enrollments_subjects_weeks"],
            deps=[int_extracts__student_enrollments_subjects],
            automation_condition=translator.get_automation_condition(view_props),
            tags=translator.get_tags(view_props),
        )
        def int_extracts__student_enrollments_subjects_weeks():
            return 2

        @asset(
            key=["kipptaf", "int_topline__star_assessment_weekly"],
            deps=[int_extracts__student_enrollments_subjects_weeks],
            automation_condition=translator.get_automation_condition(target_props),
            tags=translator.get_tags(target_props),
        )
        def int_topline__star_assessment_weekly():
            return 3

        instance = DagsterInstance.ephemeral()
        all_assets = [
            int_extracts__student_enrollments_subjects,
            int_extracts__student_enrollments_subjects_weeks,
            int_topline__star_assessment_weekly,
        ]
        defs = Definitions(assets=all_assets)

        materialize(assets=all_assets, instance=instance)
        result = evaluate_automation_conditions(defs=defs, instance=instance)
        assert result.total_requested == 0

        materialize(
            assets=[int_extracts__student_enrollments_subjects],
            instance=instance,
            selection=[int_extracts__student_enrollments_subjects],
        )
        result = evaluate_automation_conditions(
            defs=defs, instance=instance, cursor=result.cursor
        )
        assert (
            result.get_num_requested(
                AssetKey(
                    ["kipptaf", "int_extracts__student_enrollments_subjects_weeks"]
                )
            )
            == 0
        )
        assert (
            result.get_num_requested(
                AssetKey(["kipptaf", "int_topline__star_assessment_weekly"])
            )
            == 1
        )

    def test_kipptaf_double_view_chain(self, translator, nodes_by_name):
        """Real topology: int_extracts__student_enrollments_subjects (table) →
        int_students__dibels_participation_roster (view) →
        int_amplify__pm_met_criteria (view) →
        int_topline__dibels_pm_weekly (table).

        Both views should NOT be requested; target table SHOULD be requested.
        """
        source_props = self._get_node(
            nodes_by_name, "int_extracts__student_enrollments_subjects"
        )
        view_a_props = self._get_node(
            nodes_by_name, "int_students__dibels_participation_roster"
        )
        view_b_props = self._get_node(nodes_by_name, "int_amplify__pm_met_criteria")
        target_props = self._get_node(nodes_by_name, "int_topline__dibels_pm_weekly")

        @asset(
            key=["kipptaf", "int_extracts__student_enrollments_subjects"],
            tags=translator.get_tags(source_props),
        )
        def int_extracts__student_enrollments_subjects():
            return 1

        @asset(
            key=["kipptaf", "int_students__dibels_participation_roster"],
            deps=[int_extracts__student_enrollments_subjects],
            automation_condition=translator.get_automation_condition(view_a_props),
            tags=translator.get_tags(view_a_props),
        )
        def int_students__dibels_participation_roster():
            return 2

        @asset(
            key=["kipptaf", "int_amplify__pm_met_criteria"],
            deps=[int_students__dibels_participation_roster],
            automation_condition=translator.get_automation_condition(view_b_props),
            tags=translator.get_tags(view_b_props),
        )
        def int_amplify__pm_met_criteria():
            return 3

        @asset(
            key=["kipptaf", "int_topline__dibels_pm_weekly"],
            deps=[int_amplify__pm_met_criteria],
            automation_condition=translator.get_automation_condition(target_props),
            tags=translator.get_tags(target_props),
        )
        def int_topline__dibels_pm_weekly():
            return 4

        instance = DagsterInstance.ephemeral()
        all_assets = [
            int_extracts__student_enrollments_subjects,
            int_students__dibels_participation_roster,
            int_amplify__pm_met_criteria,
            int_topline__dibels_pm_weekly,
        ]
        defs = Definitions(assets=all_assets)

        materialize(assets=all_assets, instance=instance)
        result = evaluate_automation_conditions(defs=defs, instance=instance)

        materialize(
            assets=[int_extracts__student_enrollments_subjects],
            instance=instance,
            selection=[int_extracts__student_enrollments_subjects],
        )
        result = evaluate_automation_conditions(
            defs=defs, instance=instance, cursor=result.cursor
        )

        assert (
            result.get_num_requested(
                AssetKey(["kipptaf", "int_students__dibels_participation_roster"])
            )
            == 0
        )
        assert (
            result.get_num_requested(
                AssetKey(["kipptaf", "int_amplify__pm_met_criteria"])
            )
            == 0
        )
        assert (
            result.get_num_requested(
                AssetKey(["kipptaf", "int_topline__dibels_pm_weekly"])
            )
            == 1
        )

    def test_kipptaf_update_propagates_through_view_between_tables(
        self, translator, nodes_by_name
    ):
        """Real topology: stg_powerschool__terms (table) →
        int_extracts__student_enrollments_subjects (table) →
        int_extracts__student_enrollments_subjects_weeks (view) →
        int_topline__star_assessment_weekly (table).

        When source table is updated, middle table and downstream table should
        be requested; view should NOT be requested.
        """
        source_props = self._get_node(nodes_by_name, "stg_powerschool__terms")
        middle_props = self._get_node(
            nodes_by_name, "int_extracts__student_enrollments_subjects"
        )
        view_props = self._get_node(
            nodes_by_name, "int_extracts__student_enrollments_subjects_weeks"
        )
        target_props = self._get_node(
            nodes_by_name, "int_topline__star_assessment_weekly"
        )

        @asset(
            key=["kipptaf", "stg_powerschool__terms"],
            tags=translator.get_tags(source_props),
        )
        def stg_powerschool__terms():
            return 1

        @asset(
            key=["kipptaf", "int_extracts__student_enrollments_subjects"],
            deps=[stg_powerschool__terms],
            automation_condition=translator.get_automation_condition(middle_props),
            tags=translator.get_tags(middle_props),
        )
        def int_extracts__student_enrollments_subjects():
            return 2

        @asset(
            key=["kipptaf", "int_extracts__student_enrollments_subjects_weeks"],
            deps=[int_extracts__student_enrollments_subjects],
            automation_condition=translator.get_automation_condition(view_props),
            tags=translator.get_tags(view_props),
        )
        def int_extracts__student_enrollments_subjects_weeks():
            return 3

        @asset(
            key=["kipptaf", "int_topline__star_assessment_weekly"],
            deps=[int_extracts__student_enrollments_subjects_weeks],
            automation_condition=translator.get_automation_condition(target_props),
            tags=translator.get_tags(target_props),
        )
        def int_topline__star_assessment_weekly():
            return 4

        instance = DagsterInstance.ephemeral()
        all_assets = [
            stg_powerschool__terms,
            int_extracts__student_enrollments_subjects,
            int_extracts__student_enrollments_subjects_weeks,
            int_topline__star_assessment_weekly,
        ]
        defs = Definitions(assets=all_assets)

        materialize(assets=all_assets, instance=instance)
        result = evaluate_automation_conditions(defs=defs, instance=instance)
        assert result.total_requested == 0

        materialize(
            assets=[stg_powerschool__terms],
            instance=instance,
            selection=[stg_powerschool__terms],
        )
        result = evaluate_automation_conditions(
            defs=defs, instance=instance, cursor=result.cursor
        )

        assert (
            result.get_num_requested(
                AssetKey(["kipptaf", "int_extracts__student_enrollments_subjects"])
            )
            == 1
        )
        assert (
            result.get_num_requested(
                AssetKey(
                    ["kipptaf", "int_extracts__student_enrollments_subjects_weeks"]
                )
            )
            == 0
        )
        assert (
            result.get_num_requested(
                AssetKey(["kipptaf", "int_topline__star_assessment_weekly"])
            )
            == 1
        )

    def test_kipptaf_view_requested_on_code_version_change(
        self, translator, nodes_by_name
    ):
        """Real topology: stg_smartrecruiters__applications (table) →
        rpt_tableau__smartrecruiters (view).

        View should be requested when its code version changes.
        """
        upstream_props = self._get_node(
            nodes_by_name, "stg_smartrecruiters__applications"
        )
        view_props = self._get_node(nodes_by_name, "rpt_tableau__smartrecruiters")

        @asset(
            key=["kipptaf", "stg_smartrecruiters__applications"],
            tags=translator.get_tags(upstream_props),
        )
        def stg_smartrecruiters__applications():
            return 1

        @asset(
            key=["kipptaf", "rpt_tableau__smartrecruiters"],
            deps=[stg_smartrecruiters__applications],
            automation_condition=translator.get_automation_condition(view_props),
            code_version="1",
            tags=translator.get_tags(view_props),
        )
        def rpt_tableau__smartrecruiters():
            return 2

        instance = DagsterInstance.ephemeral()
        all_assets = [stg_smartrecruiters__applications, rpt_tableau__smartrecruiters]
        defs = Definitions(assets=all_assets)

        materialize(assets=all_assets, instance=instance)
        result = evaluate_automation_conditions(defs=defs, instance=instance)
        assert (
            result.get_num_requested(
                AssetKey(["kipptaf", "rpt_tableau__smartrecruiters"])
            )
            == 0
        )

        # Simulate code version change
        @asset(
            key=["kipptaf", "rpt_tableau__smartrecruiters"],
            deps=[stg_smartrecruiters__applications],
            automation_condition=translator.get_automation_condition(view_props),
            code_version="2",
            tags=translator.get_tags(view_props),
        )
        def rpt_tableau__smartrecruiters_v2():
            return 2

        defs_v2 = Definitions(
            assets=[stg_smartrecruiters__applications, rpt_tableau__smartrecruiters_v2]
        )
        result = evaluate_automation_conditions(
            defs=defs_v2, instance=instance, cursor=result.cursor
        )
        assert (
            result.get_num_requested(
                AssetKey(["kipptaf", "rpt_tableau__smartrecruiters"])
            )
            == 1
        )
