import json
from datetime import date, datetime, timedelta
from decimal import Decimal

from dagster import TimeWindowPartitionsDefinition
from dagster._utils.partitions import DEFAULT_DATE_FORMAT
from dateutil.relativedelta import relativedelta


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (timedelta, Decimal, bytes)):
            return str(o)
        elif isinstance(o, datetime):
            return o.date().isoformat()
        elif isinstance(o, date):
            return o.isoformat()
        else:
            return super().default(o)


class FiscalYear:
    def __init__(self, datetime: datetime, start_month: int) -> None:
        self.fiscal_year = (
            (datetime.year + 1) if datetime.month >= start_month else datetime.year
        )

        self.start = date(year=(self.fiscal_year - 1), month=start_month, day=1)

        self.end = self.start + relativedelta(years=1) - relativedelta(days=1)


class FiscalYearPartitionsDefinition(TimeWindowPartitionsDefinition):
    def __new__(
        cls,
        start_month: int,
        start_date: datetime | str,
        end_date: datetime | str | None = None,
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
            end=end_date,
            end_offset=end_offset,
        )
