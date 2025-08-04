import datetime

from dagster import (
    AutomationCondition,
    DagsterInstance,
    Definitions,
    asset,
    evaluate_automation_conditions,
    materialize,
)


def test_foo():
    from teamster.libraries.dbt.dagster_dbt_translator import (
        DbtTableAutomationCondition,
    )

    test_table_ac = (
        DbtTableAutomationCondition.in_latest_time_window()
        & (
            DbtTableAutomationCondition.newly_missing()
            | DbtTableAutomationCondition.code_version_changed()
            | DbtTableAutomationCondition.any_deps_updated()
        ).since(
            DbtTableAutomationCondition.newly_requested()
            | DbtTableAutomationCondition.newly_updated()
        )
        & ~DbtTableAutomationCondition.any_deps_missing()
        & ~DbtTableAutomationCondition.any_deps_in_progress()
        & ~DbtTableAutomationCondition.in_progress()
    )

    test_view_ac = (
        AutomationCondition.in_latest_time_window()
        & (
            AutomationCondition.newly_missing()
            | AutomationCondition.code_version_changed()
        ).since(
            AutomationCondition.newly_requested() | AutomationCondition.newly_updated()
        )
        & ~AutomationCondition.any_deps_missing()
        & ~AutomationCondition.any_deps_in_progress()
        & ~AutomationCondition.in_progress()
    )

    @asset(
        automation_condition=test_table_ac,
        metadata={"dagster-dbt/materialization_type": "table"},
    )
    def upstream_table():
        return

    @asset(
        deps=[upstream_table],
        automation_condition=test_view_ac,
        metadata={"dagster-dbt/materialization_type": "view"},
    )
    def intermediate_view():
        return

    @asset(
        deps=[intermediate_view],
        automation_condition=test_table_ac,
        metadata={"dagster-dbt/materialization_type": "table"},
    )
    def downstream_table():
        return

    instance = DagsterInstance.ephemeral()

    # On the first tick, request because assets are missing
    eval_result_1 = evaluate_automation_conditions(
        defs=[upstream_table, intermediate_view, downstream_table], instance=instance
    )
    assert eval_result_1.total_requested == 3

    # materialize
    materialization_result = materialize(
        assets=[upstream_table, intermediate_view, downstream_table], instance=instance
    )
    assert materialization_result.success

    updated_cursor = eval_result_1.cursor.with_updates(
        evaluation_id=eval_result_1.cursor.evaluation_id + 1,
        evaluation_timestamp=datetime.datetime.now().timestamp(),
        newly_observe_requested_asset_keys=[
            r.key
            for r in eval_result_1.results
            if r.true_subset.get_internal_bool_value()
        ],
        condition_cursors=[result.get_new_cursor() for result in eval_result_1.results],
        asset_graph=Definitions(
            assets=[upstream_table, intermediate_view, downstream_table]
        ).resolve_asset_graph(),
    )

    # on second tick, only downstream_table requested
    eval_result_2 = evaluate_automation_conditions(
        defs=[upstream_table, intermediate_view, downstream_table],
        instance=instance,
        cursor=updated_cursor,
    )

    assert {
        r.key for r in eval_result_2.results if r.true_subset.get_internal_bool_value()
    } == {downstream_table.key}
