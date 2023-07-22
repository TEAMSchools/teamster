import pendulum

from teamster.core.utils.classes import FiscalYear

CODE_LOCATION = "kippmiami"
GCS_PROJECT_NAME = "teamster-332318"

LOCAL_TIMEZONE = pendulum.timezone(name="America/New_York")
NOW = pendulum.now(tz=LOCAL_TIMEZONE)
TODAY = NOW.start_of(unit="day")
CURRENT_FISCAL_YEAR = FiscalYear(datetime=TODAY, start_month=7)
