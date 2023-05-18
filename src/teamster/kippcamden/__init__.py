import pendulum

from teamster.core.utils.classes import FiscalYear

CODE_LOCATION = "kippcamden"

LOCAL_TIMEZONE = pendulum.timezone(name="US/Eastern")
NOW = pendulum.now(tz=LOCAL_TIMEZONE)
TODAY = NOW.start_of(unit="day")
CURRENT_FISCAL_YEAR = FiscalYear(datetime=TODAY, start_month=7)
