# Fiscal Year & Partitioning

## Fiscal year

KIPP TEAM & Family Schools uses a **July 1 fiscal year**. The `FiscalYear`
utility class in `src/teamster/core/utils/classes.py` encapsulates this logic:

```python
from teamster.core.utils.classes import FiscalYear
from datetime import datetime

fy = FiscalYear(datetime(2025, 9, 1), start_month=7)
fy.fiscal_year  # 2026
fy.start        # date(2025, 7, 1)
fy.end          # date(2026, 6, 30)
```

A date on or after July 1 belongs to the **next** fiscal year. For example,
September 2025 is in fiscal year 2026 (FY26).

## Partitioned assets

### `FiscalYearPartitionsDefinition`

A `TimeWindowPartitionsDefinition` subclass that creates one partition per
fiscal year, starting on July 1:

```python
from teamster.core.utils.classes import FiscalYearPartitionsDefinition

partitions = FiscalYearPartitionsDefinition(
    start_month=7,
    start_date="2019-07-01",
)
# Partitions: 2019-07-01, 2020-07-01, 2021-07-01, ...
```

### Date-partitioned assets

Most source system assets (PowerSchool, Deanslist, iReady, etc.) use
`DailyPartitionsDefinition` or `MonthlyPartitionsDefinition`. These produce
partition keys like `2025-09-01`, which the `GCSIOManager` decomposes into
Hive-style paths:

```text
_dagster_partition_fiscal_year=2026/
  _dagster_partition_date=2025-09-01/
    _dagster_partition_hour=00/
      _dagster_partition_minute=00/
        data
```

### Static-partitioned assets

Some assets use `StaticPartitionsDefinition` for a fixed set of values (e.g.
school IDs, report types). These produce paths like:

```text
_dagster_partition_key=<value>/data
```

### Multi-partitioned assets

Assets with multiple partition dimensions (e.g. date × school) use
`MultiPartitionsDefinition`. The `GCSIOManager` concatenates all dimensions
sorted alphabetically by dimension name.

## `date_to_fiscal_year()` dbt macro

Use this macro in SQL to compute a fiscal year from a date column:

```sql
{{
    date_to_fiscal_year(
        date_field="entry_date", start_month=7, year_source="start"
    )
}} as academic_year
```

- `year_source="start"` — returns the calendar year the fiscal year **starts**
  in (e.g. a date in July 2025 → `2025`)
- `year_source="end"` — returns the calendar year the fiscal year **ends** in
  (e.g. a date in July 2025 → `2026`)

## Checking whether an asset is incremental

On an asset's detail page in Dagster Cloud, the **Metadata** tab shows a
`partition_column` key. If the value is `null`, the asset runs as a full
overnight refresh rather than an incremental update. A non-null value is the
column name used to filter rows for the current partition.

## `current_fiscal_year` and `current_academic_year`

Each code location's `__init__.py` defines `CURRENT_FISCAL_YEAR` (an `int`).
This is passed to dbt as a project variable:

```python
# src/teamster/code_locations/kipptaf/__init__.py
CURRENT_FISCAL_YEAR = 2026
```

dbt models access this via `{{ var("current_fiscal_year") }}`. The
`current_academic_year` var is `CURRENT_FISCAL_YEAR - 1` (i.e. the school year
that started in the prior calendar year).
