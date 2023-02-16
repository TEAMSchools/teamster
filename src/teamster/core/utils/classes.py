import datetime
import decimal
import json

import pendulum


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
