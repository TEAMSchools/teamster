import pendulum
from pendulum import timezone

from teamster.core.utils.classes import FiscalYear

CODE_LOCATION = "kipptaf"

LOCAL_TIMEZONE = timezone("America/New_York")
CURRENT_FISCAL_YEAR = FiscalYear(datetime=pendulum.today(LOCAL_TIMEZONE), start_month=7)