from dagster import DagsterInstance, build_schedule_context


def _test_dbt_code_version_schedule(schedule):
    context = build_schedule_context(
        instance=DagsterInstance.from_config(
            config_dir=".dagster/home", config_filename="dagster-cloud.yaml"
        )
    )

    output = schedule(context=context)

    context.log.info(output)
