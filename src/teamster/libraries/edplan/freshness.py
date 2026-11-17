from datetime import timedelta

from dagster import FreshnessPolicy

# For each NJ district's stg_edplan__njsmart_powerschool. Staging tolerates
# partition gaps (see the model's properties yml) and normally rebuilds only when
# a new daily file lands, so a failed policy usually means EdPlan skipped a day
# or the sensor stopped. A code-version change or manual run in the window also
# counts as fresh and can hide a skipped day. Every district's file lands
# overnight; Paterson also gets a midday file, which this window does not need.
STAGING_FRESHNESS_POLICY = FreshnessPolicy.cron(
    deadline_cron="0 6 * * *",
    lower_bound_delta=timedelta(hours=24),
    timezone="America/New_York",
)
