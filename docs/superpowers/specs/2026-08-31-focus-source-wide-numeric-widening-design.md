# Widen every unbounded Focus numeric and delete the per-table opt-in

Design for [#5080](https://github.com/TEAMSchools/teamster/issues/5080).
Measured against prod on 2026-08-31.

## Problem

An unbounded Postgres `numeric` reflects as `precision=None`. dlt renders that
as `decimal128(38, 9)`, and pyarrow refuses to rescale a value carrying more
than 9 decimal places. The extract dies:

```text
PyToArrowConversionException: Conversion to arrow failed for field `points`
with dlt hint `data_type=decimal` and `inferred_arrow_type=decimal128(38, 9)`
Insufficient decimal precision Rescaling Decimal value would cause data loss
```

Every Focus table loads in one Dagster step, `kippmiami__dlt__focus`, so one bad
column stops all 20 tables in the run.

It has happened twice. `student_gpa_calculated.weighted_gpa` broke the first
load of a new table in
[#5021](https://github.com/TEAMSchools/teamster/issues/5021).
`gradebook_grades.points` broke a table that had loaded for months, in
[#5074](https://github.com/TEAMSchools/teamster/issues/5074), and cost 2 days of
downtime.

The current fix is opt-in. A table gets `widen_unbounded_numeric: true` in
`config/focus.yaml` only after it breaks. That opt-in exists for one reason:
widening retypes the column to BigQuery BIGNUMERIC, and the `replace` write
disposition cannot retype a column in place, so an already-loaded table must be
dropped and reloaded.

## Measurement

### 191 columns across 45 tables can still fail

dlt stores its full reflected schema in
`dagster_kippmiami_dlt_focus._dlt_version.schema`. Reading the newest row,
version 356, written 2026-08-28:

| precision, scale | columns | meaning                                       |
| ---------------- | ------- | --------------------------------------------- |
| 38, 9            | 191     | dlt's default for an unbounded `numeric`      |
| 76, 38           | 16      | already widened, all `student_gpa_calculated` |
| declared values  | 9       | real precision in Postgres, cannot overflow   |

`gradebook_grades.points` appears in the 191. That is what proves `(38, 9)`
marks an unbounded column rather than a column declared `numeric(38, 9)`.

The full per-table list is in the
[#5074 comment](https://github.com/TEAMSchools/teamster/issues/5074#issuecomment-5480205285).
The largest concentrations are `students` at 25 columns, `users` at 22,
`school_periods` at 16, and `schedule` and `schools` at 12 each.

### The extra precision is discarded one layer later

Nothing reads `dagster_kippmiami_dlt_focus` except the `focus` dbt source, and
only `stg_focus__*` models read that source. Every affected staging model casts
the column back to `numeric`, and BigQuery NUMERIC is `(38, 9)`.

So a widened column carries 38 decimal places in the raw table and 9 everywhere
a dashboard or a person can see it. Widening buys crash-avoidance. It buys no
extra precision downstream.

### 96 of the 191 columns need a cast

A column needs `cast(<col> as numeric)` only if a staging model projects it.

|                                                 | count |
| ----------------------------------------------- | ----- |
| unbounded columns                               | 191   |
| projected by a staging model, so needing a cast | 96    |
| staging models to edit                          | 41    |
| casts on aliased projections                    | 5     |

The 95 unprojected columns still become BIGNUMERIC in BigQuery, harmlessly. They
are mostly `custom_*` fields on `students`, `users`, and `schools`, plus the
`length_*` family on `school_periods` and the `min_score*` and `max_score*`
families on `test_history_score_types`.

The 5 aliased projections look like
`custom_200000002 as experience_length_years` in `stg_focus__users.sql` and
become `cast(custom_200000002 as numeric) as experience_length_years`.

`discipline_incidents` has an unbounded column and is loaded, but has no staging
model at all. Nothing to do there.

### The reload is small

The 45 tables hold 799,554 rows and 173 MB, largest table 371,411 rows. Recent
full syncs of 20 tables completed in 2 to 3 minutes, so a 45-table reload runs
in minutes.

### Focus has no `double precision` columns

The reflected schema holds 216 `decimal` columns and 0 `double`. The adapter's
`Float` guard is therefore dead code today.

It stays anyway. `Float` subclasses `Numeric` and also reflects
`precision=None`, so without the guard a future `double precision` column would
land as BIGNUMERIC. Source-wide widening raises that guard's coverage from 2
tables to all 79.

## Why widen rather than round in the query

`_focus_table_items` already passes `query_adapter_callback=None` to
`table_rows`. Wiring it to emit `round(col, 9)` for unbounded numeric columns
would make the crash impossible with no retype, no reload, and no casts, and
every downstream value would be identical, because dbt rounds to 9 places either
way.

That option is rejected deliberately. The raw dlt layer should hold what
Postgres holds. Rounding at extract makes the warehouse quietly disagree with
the source, and the disagreement would be invisible.

## Design

### The type adapter becomes unconditional

`_widening_type_adapter` becomes the only adapter every table gets. Everything
that existed to route between two adapters is deleted.

| file                                                   | change                                                                                                                                                                                                                              |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `libraries/dlt/focus/assets.py`                        | drop the `type_adapter` parameter from `_focus_table_items`, `widen_numeric` from `_build_focus_resource`, and `widen_numeric_tables` from `build_focus_source` and `build_focus_dlt_assets`. Always pass `_widening_type_adapter`. |
| `code_locations/kippmiami/dlt/focus/assets.py`         | delete the `widen_numeric_tables` frozenset and its docstring                                                                                                                                                                       |
| `code_locations/kippmiami/dlt/focus/config/focus.yaml` | delete both `widen_unbounded_numeric: true` keys and their comments                                                                                                                                                                 |
| `tests/libraries/test_dlt_focus_type_adapter.py`       | delete `test_widen_numeric_flag_selects_the_type_adapter`, replace with one asserting every table reaches `table_rows` with `_widening_type_adapter`                                                                                |

The function keeps the name `_widening_type_adapter`, which still describes what
it does. Only its docstring is wrong, because it says "for tables that opt into
numeric widening". The `Float` guard gains a comment recording that it now
covers all 79 tables.

### The 96 casts

Each cast follows the shape already used by
`stg_focus__student_gpa_calculated.sql`: plain column references first, a blank
line, then the casts, then `from`. Each cast carries an explicit alias.

```sql
    updated_at,

    cast(points as numeric) as points,
    cast(possible_points as numeric) as possible_points,
from {{ source("focus", "gradebook_grades") }}
```

Generate the edits with a script rather than by hand across 41 files. The script
must assert that each anchor matches exactly once and abort otherwise.

No `.yml` properties file changes. Every affected column already declares
`data_type: numeric`, and the cast preserves both the name and the declared
type, so this is not a breaking change.

## Cutover

Two pull requests, then one manual run.

1. Merge the dbt pull request. The casts are no-ops against today's NUMERIC
   columns, so this is safe on its own and can sit merged for any length of
   time.
1. Merge the Dagster pull request. Wait for the `kippmiami` code location to
   redeploy.
1. Launch one manual Focus run over all 79 tables with run config
   `refresh: drop_resources`.

Order matters. The moment the Dagster change deploys, a load writes BIGNUMERIC
into columns whose staging contracts still declare `numeric`, so the casts must
already be in place.

All 79 tables rather than only the 45, deliberately. The 45-table list comes
from a schema snapshot written 2026-08-28, so a column added since would be
missed. Reloading everything is self-correcting and the dataset is small.

Sensor ticks landing between the deploy and the reload fail harmlessly. dlt
commits resource state only from resources that reached the load package, so a
failed load keeps the old baseline and the table re-selects on the next tick.
The cost is 1 or 2 red runs and their alerts. No sensor or schedule is paused.

Step 3 is a destructive shared-resource mutation and must be launched by a
person from the Dagster UI.

## Verification

- Before the cutover, `INFORMATION_SCHEMA.COLUMNS` shows the 191 columns as
  NUMERIC across the 45 tables.
- After, those same 191 read BIGNUMERIC, and every table in the dataset still
  exists with its row count intact.
- `dbt build --select package:focus` is green, with contracts enforced on
  `focus.staging`.
- `tests/libraries/test_dlt_focus_type_adapter.py` is green.
- One intraday sensor tick runs clean end to end.

## Risks

`dataset_name` is not branch-isolated. A branch deployment writes to the same
BigQuery dataset as prod, so the reload cannot be rehearsed anywhere. The
mitigation is that `refresh: drop_resources` is proven in this repo already,
from [#4740](https://github.com/TEAMSchools/teamster/issues/4740), and the
reload is small enough to repeat if it goes wrong.

A missed cast breaks a contract, which fails CI. It does not corrupt data.

The [#5075](https://github.com/TEAMSchools/teamster/pull/5075) fix adds 2 of the
96 casts, on `gradebook_grades`. If it merges first, this work carries 94.

## Out of scope

Illuminate has its own `unbounded_numeric_adapter` at `(38, 18)` against Focus's
`(76, 38)`. After this change both are source-wide and do the same job at
different scales. Converging them is unrelated refactoring and is left alone.
