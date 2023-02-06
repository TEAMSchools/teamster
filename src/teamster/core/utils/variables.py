import pendulum

LOCAL_TIME_ZONE = pendulum.timezone(name="US/Eastern")
NOW = pendulum.now(tz=LOCAL_TIME_ZONE)
TODAY = NOW.start_of(unit="day")
