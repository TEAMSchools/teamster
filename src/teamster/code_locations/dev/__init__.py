from datetime import datetime
from zoneinfo import ZoneInfo

from teamster.core.utils.classes import FiscalYear

CODE_LOCATION = "dev"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")

CURRENT_FISCAL_YEAR = FiscalYear(datetime=datetime.now(LOCAL_TIMEZONE), start_month=7)
