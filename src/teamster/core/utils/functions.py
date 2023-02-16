import pendulum


def fiscal_year_dates(datetime, start_month):
    fiscal_year = (
        (datetime.year + 1) if datetime.month >= start_month else datetime.year
    )

    start_date = pendulum.date(year=(fiscal_year - 1), month=start_month, day=1)

    return {"start": start_date, "end": start_date.add(years=1).subtract(days=1)}
