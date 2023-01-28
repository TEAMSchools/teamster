import os

import pendulum

LOCAL_TIME_ZONE = pendulum.timezone(name=os.getenv("LOCAL_TIME_ZONE"))
NOW = pendulum.now(tz=LOCAL_TIME_ZONE)
TODAY = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
