import json
from datetime import date, datetime, timedelta
from decimal import Decimal

from dagster import TimeWindowPartitionsDefinition
from dagster._core.definitions.partition import DEFAULT_DATE_FORMAT
from pendulum import Date, DateTime, Duration


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (timedelta, Decimal, bytes, Duration)):
            return str(o)
        elif isinstance(o, (DateTime, Date)):
            return o.for_json()
        elif isinstance(o, (datetime, date)):
            return o.isoformat()
        else:
            return super().default(o)


class FiscalYear:
    def __init__(self, datetime: DateTime, start_month: int) -> None:
        self.fiscal_year = (
            (datetime.year + 1) if datetime.month >= start_month else datetime.year
        )

        self.start = Date(year=(self.fiscal_year - 1), month=start_month, day=1)

        self.end = self.start.add(years=1).subtract(days=1)


class FiscalYearPartitionsDefinition(TimeWindowPartitionsDefinition):
    def __new__(
        cls,
        start_date: DateTime | str,
        start_month: int,
        timezone: str | None = None,
        start_day: int = 1,
        fmt: str | None = None,
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
