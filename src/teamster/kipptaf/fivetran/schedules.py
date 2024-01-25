from dagster import ScheduleEvaluationContext, SkipReason, schedule
from dagster_fivetran import FivetranResource

from .. import CODE_LOCATION, LOCAL_TIMEZONE


def build_fivetran_start_sync_schedule(
    code_location, connector_id, connector_name, cron_schedule, execution_timezone
):
    @schedule(
        name=f"{code_location}_fivetran_sync_{connector_name}_schedule",
        cron_schedule=cron_schedule,
        execution_timezone=execution_timezone,
        job_name="",
    )  # type: ignore
    def _schedule(context: ScheduleEvaluationContext, fivetran: FivetranResource):
        fivetran.start_sync(connector_id=connector_id)
        return SkipReason("This schedule doesn't actually return any runs.")

    return _schedule


def build_fivetran_start_resync_schedule(
    code_location, connector_id, connector_name, cron_schedule, execution_timezone
):
    @schedule(
        name=f"{code_location}_fivetran_resync_{connector_name}_schedule",
        cron_schedule=cron_schedule,
        execution_timezone=execution_timezone,
        job_name="",
    )  # type: ignore
    def _schedule(context: ScheduleEvaluationContext, fivetran: FivetranResource):
        fivetran.start_resync(connector_id=connector_id)
        return SkipReason("This schedule doesn't actually return any runs.")

    return _schedule


adp_workforce_now_start_resync_schedule = build_fivetran_start_resync_schedule(
    code_location=CODE_LOCATION,
    connector_id="sameness_cunning",
    connector_name="adp_workforce_now",
    cron_schedule="0 20 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

adp_workforce_now_start_sync_schedule = build_fivetran_start_sync_schedule(
    code_location=CODE_LOCATION,
    connector_id="sameness_cunning",
    connector_name="adp_workforce_now",
    cron_schedule="0 0-19 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

illuminate_start_sync_schedule = build_fivetran_start_sync_schedule(
    code_location=CODE_LOCATION,
    connector_id="jinx_credulous",
    connector_name="illuminate",
    cron_schedule="5 * * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

illuminate_xmin_start_sync_schedule = build_fivetran_start_sync_schedule(
    code_location=CODE_LOCATION,
    connector_id="genuine_describing",
    connector_name="illuminate_xmin",
    cron_schedule="0 * * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

coupa_start_sync_schedule = build_fivetran_start_sync_schedule(
    code_location=CODE_LOCATION,
    connector_id="bellows_curliness",
    connector_name="coupa",
    cron_schedule="0 * * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

facebook_pages_start_sync_schedule = build_fivetran_start_sync_schedule(
    code_location=CODE_LOCATION,
    connector_id="regency_carrying",
    connector_name="facebook_pages",
    cron_schedule="0 * * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

instagram_business_start_sync_schedule = build_fivetran_start_sync_schedule(
    code_location=CODE_LOCATION,
    connector_id="muskiness_cumulative",
    connector_name="instagram_business",
    cron_schedule="0 * * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

_all = [
    adp_workforce_now_start_resync_schedule,
    adp_workforce_now_start_sync_schedule,
    coupa_start_sync_schedule,
    facebook_pages_start_sync_schedule,
    illuminate_start_sync_schedule,
    illuminate_xmin_start_sync_schedule,
    instagram_business_start_sync_schedule,
]
