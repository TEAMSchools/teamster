from dagster import (
    AutomationCondition,
    DagsterInstance,
    asset,
    evaluate_automation_conditions,
    materialize,
)


def test_policy_blank_slate() -> None:
    @asset()
    def upstream_asset() -> None:
        return

    @asset(
        deps=[upstream_asset],
        automation_condition=(
            AutomationCondition.eager() | AutomationCondition.code_version_changed()
        ),
    )
    def table_upstream() -> None:
        return

    @asset(
        deps=[table_upstream],
        automation_condition=AutomationCondition.newly_missing()
        | AutomationCondition.code_version_changed(),
    )
    def view() -> None:
        return

    @asset(
        deps=[view],
        automation_condition=(
            AutomationCondition.eager() | AutomationCondition.code_version_changed()
        ),
    )
    def table_downstream() -> None:
        return

    instance = DagsterInstance.ephemeral()

    # all 3 downstream materialize on initial run
    materialize(assets=[upstream_asset], instance=instance)

    result = evaluate_automation_conditions(
        defs=[table_upstream, view, table_downstream], instance=instance
    )

    assert result.total_requested == 3

    # tables materialized but view is skipped on subsequent run
    materialize(assets=[upstream_asset], instance=instance)

    result = evaluate_automation_conditions(
        defs=[table_upstream, view, table_downstream],
        instance=instance,
        cursor=result.cursor,
    )

    assert result._requested_partitions_by_asset_key.keys() == [
        table_upstream.key,
        table_downstream.key,
    ]
