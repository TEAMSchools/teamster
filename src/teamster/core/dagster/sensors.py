from dagster import RunFailureSensorContext, run_failure_sensor


@run_failure_sensor
def run_execution_interrupted_sensor(context: RunFailureSensorContext):
    for event in context.get_step_failure_events():
        context.log.info(event)
