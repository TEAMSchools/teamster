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
