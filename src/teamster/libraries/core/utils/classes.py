import datetime
import decimal
import json
from typing import Optional, Union

import pendulum
from dagster import TimeWindowPartitionsDefinition
from dagster._core.definitions.partition import DEFAULT_DATE_FORMAT


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(
            o, (datetime.timedelta, decimal.Decimal, bytes, pendulum.Duration)
        ):
            return str(o)
        elif isinstance(o, (pendulum.DateTime, pendulum.Date)):
            return o.for_json()
        elif isinstance(o, (datetime.datetime, datetime.date)):
            return o.isoformat()
        else:
            return super().default(o)


class FiscalYear:
    def __init__(self, datetime, start_month) -> None:
        self.fiscal_year = (
            (datetime.year + 1) if datetime.month >= start_month else datetime.year
        )
        self.start = pendulum.date(
            year=(self.fiscal_year - 1), month=start_month, day=1
        )
        self.end = self.start.add(years=1).subtract(days=1)


class FiscalYearPartitionsDefinition(TimeWindowPartitionsDefinition):
    def __new__(
        cls,
        start_date: Union[pendulum.DateTime, str],
        start_month: int,
        timezone: Optional[str],
        start_day: int = 1,
        fmt: Optional[str] = None,
        end_offset: int = 1,
    ):
        _fmt = fmt or DEFAULT_DATE_FORMAT

        return super(FiscalYearPartitionsDefinition, cls).__new__(
            cls,
            cron_schedule=f"0 0 {start_day} {start_month} *",
            timezone=timezone,
            fmt=_fmt,
            start=start_date,
            end_offset=end_offset,
        )
