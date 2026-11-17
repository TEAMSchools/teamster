from datetime import timedelta

from dagster import FreshnessPolicy

# For each NJ district's stg_edplan__njsmart_powerschool. Staging rebuilds only
# when a new daily file lands (it tolerates partition gaps, see the model's
# properties yml), so a failed policy means EdPlan skipped a day or the sensor
# stopped. Every district's file lands overnight; Paterson also gets a midday
# file, which this window does not require.
STAGING_FRESHNESS_POLICY = FreshnessPolicy.cron(
    deadline_cron="0 6 * * *",
    lower_bound_delta=timedelta(hours=24),
    timezone="America/New_York",
)
