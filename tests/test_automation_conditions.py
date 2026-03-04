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


def _get_view_condition() -> AutomationCondition:
    return dbt_view_automation_condition(ignore_selection=_EMPTY_SELECTION)


def _get_table_condition() -> AutomationCondition:
    return dbt_table_automation_condition(ignore_selection=_EMPTY_SELECTION)


def test_view_not_requested_on_upstream_update():
    """Views should NOT be requested when an upstream table is updated."""

    @asset
    def upstream_table():
        return 1

    @asset(deps=[upstream_table], automation_condition=_get_view_condition())
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

    @asset
    def upstream_table():
        return 1

    @asset(deps=[upstream_table], automation_condition=_get_table_condition())
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


def test_table_view_table_chain():
    """Core test: Table -> View -> Table chain.

    When upstream_table is materialized:
    - intermediate_view should NOT be requested (it's a view)
    - downstream_table SHOULD be requested (sees through the view)
    """

    @asset
    def upstream_table():
        return 1

    @asset(deps=[upstream_table], automation_condition=_get_view_condition())
    def intermediate_view():
        return 2

    @asset(deps=[intermediate_view], automation_condition=_get_table_condition())
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

    @asset
    def source_table():
        return 1

    @asset(deps=[source_table], automation_condition=_get_view_condition())
    def view_a():
        return 2

    @asset(deps=[view_a], automation_condition=_get_view_condition())
    def view_b():
        return 3

    @asset(deps=[view_b], automation_condition=_get_table_condition())
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


def test_view_requested_on_code_version_change():
    """Views SHOULD be requested when their code version changes."""

    @asset
    def upstream_table():
        return 1

    @asset(
        deps=[upstream_table],
        automation_condition=_get_view_condition(),
        code_version="1",
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
    )
    def my_view_v2():
        return 2

    defs_v2 = Definitions(assets=[upstream_table, my_view_v2])
    result = evaluate_automation_conditions(
        defs=defs_v2, instance=instance, cursor=result.cursor
    )
    assert result.get_num_requested(AssetKey("my_view")) == 1
