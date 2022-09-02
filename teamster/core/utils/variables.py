import datetime
import os
from zoneinfo import ZoneInfo

LOCAL_TIME_ZONE = ZoneInfo(os.getenv("LOCAL_TIME_ZONE"))
NOW = datetime.datetime.now(tz=LOCAL_TIME_ZONE)
TODAY = TODAY = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
YESTERDAY = TODAY - datetime.timedelta(days=1)
