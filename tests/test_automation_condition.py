from dagster import (
    AssetMaterialization,
    AutomationCondition,
    DagsterInstance,
    asset,
    evaluate_automation_conditions,
)
from dagster._core.definitions.declarative_automation.automation_condition import (
    AutomationResult,
)


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


def foo(automation_result: AutomationResult, depth: int):
    depth = depth + 1

    print(
        ("." * 2 * depth) + automation_result.asset_key.to_python_identifier(),
        automation_result.condition.name,
        automation_result.true_subset.value,
    )

    if automation_result.child_results:
        for result in automation_result.child_results:
            foo(result, depth)


def test_policy() -> None:
    instance = DagsterInstance.ephemeral()

    # all 3 downstream materialize on initial run
    instance.report_runless_asset_event(
        AssetMaterialization(asset_key=upstream_asset.key)
    )

    result = evaluate_automation_conditions(
        defs=[table_upstream, view, table_downstream], instance=instance
    )

    # print("\nINITIAL RUN")
    # for automation_result in result.results:
    #     print(automation_result.asset_key.to_python_identifier())
    #     foo(automation_result, 0)

    assert result.total_requested == 3

    # materialize requested asset partitions
    for rap in result._requested_asset_partitions:
        instance.report_runless_asset_event(
            AssetMaterialization(asset_key=rap.asset_key, partition=rap.partition_key)
        )

    # tables materialized but view is skipped on subsequent run
    print("\nSUBSEQUENT RUN")
    instance.report_runless_asset_event(
        AssetMaterialization(asset_key=upstream_asset.key)
    )

    result = evaluate_automation_conditions(
        defs=[table_upstream, view, table_downstream],
        instance=instance,
        cursor=result.cursor,
    )

    for automation_result in result.results:
        print(automation_result.asset_key.to_python_identifier())
        foo(automation_result, 0)

    assert result._requested_partitions_by_asset_key.keys() == (
        [table_upstream.key, table_downstream.key]
    )
