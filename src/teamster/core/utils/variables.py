import os

import pendulum

LOCAL_TIME_ZONE = pendulum.timezone(name=os.getenv("LOCAL_TIME_ZONE"))
NOW = pendulum.now(tz=LOCAL_TIME_ZONE)
TODAY = NOW.start_of(unit="day")
