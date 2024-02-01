import pendulum
from pendulum.tz import timezone

from teamster.core.utils.classes import FiscalYear

CODE_LOCATION = "kippmiami"

LOCAL_TIMEZONE = timezone(name="America/New_York")
NOW = pendulum.now(tz=LOCAL_TIMEZONE)
TODAY = NOW.start_of(unit="day")
CURRENT_FISCAL_YEAR = FiscalYear(datetime=TODAY, start_month=7)
