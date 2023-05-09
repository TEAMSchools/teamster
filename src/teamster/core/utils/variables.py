import pendulum

from .classes import FiscalYear

LOCAL_TIME_ZONE = pendulum.timezone(name="US/Eastern")
NOW = pendulum.now(tz=LOCAL_TIME_ZONE)
TODAY = NOW.start_of(unit="day")
CURRENT_FISCAL_YEAR = FiscalYear(datetime=TODAY, start_month=7)
