# Handoff: Tesseract multi-stage "end-of-period" attendance measures

**Audience:** Cube solutions architect **Branch:**
`cristinabaldor/refactor/cube-tesseract-engine` **Status:** Blocked —
multi-stage measures will not compile against our `student_attendance` cube. The
working tree has been reverted to the legacy (working) approach; this document
captures what we were trying to do, every variation we tried, and the precise
compile errors so you can advise.

## The use case (chronic absence — a semi-additive / snapshot metric)

`fct_student_attendance_daily` has **one row per student-enrollment per calendar
day**. The chronic-absence columns are **cumulative year-to-date, re-stamped on
every daily row**:

- `is_chronically_absent` (bool) — TRUE when the enrollment's cumulative ADA
  through that date is `< 0.90`.
- `ada_tier` (string) — Tier 1/2/3/4 from the same cumulative ADA.
- `is_truant` (bool) — regional truancy rule, also cumulative.

These are **semi-additive over time**: you cannot sum/count them across days (a
student who is CA on 30 days would count 30×). A correct measure must pick **one
row per period-end per enrollment** and count those.

We want a measure (`pct_chronically_absent`, `count_chronically_absent`, ADA
tier rates) that is **grain-adaptive**: group by `academic_year` → year-end
snapshot; by month → month-end; by week → week-end — returning the cumulative
status as of each enrollment's **last full membership day** in the period.

"Period-end per enrollment" (not a global period-end date) is deliberate: a
student who exits mid-period should carry **their own** last status, not be
zeroed against a global last date. This matches the dbt windows below.

### What production does today (and why we want to replace it)

Two mechanisms, both in this repo:

1. **`queryRewrite` anchor injection** (`src/cube/cube.js`, `SNAPSHOT_CUBES` /
   `SNAPSHOT_MEASURE_STEMS`): silently injects an `is_latest_record` /
   `is_month_end_record` / `is_week_end_record` filter based on the query's
   granularity.
2. **~25 per-grain named measures** (`*_year_end` / `*_month_end` /
   `*_week_end`) that bake the anchor in.

The `is_*_record` flags are precomputed in dbt
(`fct_student_attendance_daily.sql`), per enrollment, e.g.:

```sql
row_number() over (
    partition by student_enrollment_key, date_trunc(date_key, month)
    order by if(membership_value = 1, date_key, null) desc nulls last
) = 1 and membership_value = 1 as is_month_end_record
```

A Cube engineer flagged that the `queryRewrite` rewrite is invisible to
downstream BI tools (the generated query doesn't know a filter was injected and
the semantics shift by granularity), so we tried to move period-end selection
into a single declarative measure using **Tesseract multi-stage `grain`**.

## What we tried (the target pattern)

From the unmerged docs PR
[cube-js/cube#11073](https://github.com/cube-js/cube/pull/11073) (semi-additive
recipe): a multi-stage `rank` measure that ranks each enrollment's days within
the queried period, plus measures filtered to `{rank} = 1`.

Deviation from the published recipe: we keep the **entity** in `grain.keep_only`
(per-enrollment period-end), not the recipe's global period-end.

### Best attempt (the version we most wanted to work)

```yaml
# Plain (no {CUBE}) proxy dimensions — multi-stage members cannot resolve a
# {CUBE} expression, so we proxy the raw columns:
- name: _student_enrollment_key
  sql: student_enrollment_key       # plain column
  type: string
  public: false
- name: _date_key_sort
  sql: date_key                      # plain column (attendance_date is CAST({CUBE}.date_key ...))
  type: string
  public: false

measures:
  - name: _eop_rank
    public: false
    multi_stage: true
    type: rank
    order_by:
      - sql: "IF({membership_value} = 1, {_date_key_sort}, NULL)"   # membership days first
        dir: desc
    grain:
      include:                       # leaf GROUP BY
        - _student_enrollment_key
        - _date_key_sort
        - membership_value
      keep_only:                     # window PARTITION BY = period grains + entity
        - _student_enrollment_key
        - dates.academic_year        # <-- joined-cube member (see Finding 3)
        - dates.month_number
        - dates.school_week_start_date
        # ...every date grain a query might group by

  - name: count_chronically_absent_eop
    multi_stage: true
    type: count_distinct
    sql: "{_student_enrollment_key}"
    grain:
      include:
        - _student_enrollment_key
        - _date_key_sort
    filters:
      - sql: "{_eop_rank} = 1"
      - sql: "{is_chronically_absent} = true"
      - sql: "{membership_value} = 1"
      - sql: >-
          {students.enrollment_status} != 'Transferred Out' OR NOT
          {dates.is_current_academic_year}     # <-- joined-cube refs (see Finding 2)
```

`pct_chronically_absent_eop` =
`count_chronically_absent_eop / _count_ca_eligible_students_eop` (a parallel
`count_distinct` with the same anchor + eligibility, minus the CA condition).
ADA-tier `_eop` measures are the same shape with `{ada_tier} IN (...)`.

## Findings (all reproduced locally — see "Local repro" below)

We ran a local Cube dev server with `CUBEJS_TESSERACT_SQL_PLANNER=true` and
bisected. The errors are compile-time (`/v1/sql` returns HTTP 500 with
`Compile errors`).

1. **The pattern itself is sound.** A standalone inline-SQL probe cube (no
   joins, plain-column dimensions) with `grain.include` + `grain.keep_only` + a
   `rank` measure + a consumer filtered to `{rank} = 1` **compiles cleanly**. So
   `grain`/multi-stage works; the problem is specific to `student_attendance`.

2. **A multi-stage measure cannot WRAP a base measure whose `filters` use
   `{CUBE}` or joined-cube refs.** Our first version did
   `sql: "{count_chronically_absent}"`. `count_chronically_absent`'s filters are
   `{CUBE}.membership_value = 1`, `{students.enrollment_status} ...`,
   `{dates.is_current_academic_year}`. Inlined into a multi-stage measure these
   produce:

   ```text
   Compile errors:
   _eop_rank is not defined
   student_attendance is not defined
   ```

   Confirmed: wrapping a **plain** base measure (`_sum_attendance_value`,
   `sql: attendance_value`, no filters) instead compiles cleanly.

3. **Referencing a member whose SQL contains `{CUBE}` inside multi-stage
   `order_by`/`grain` fails the same way.** `attendance_date` is
   `CAST({CUBE}.date_key AS TIMESTAMP)`. Using it in the rank → same error.
   **Fix that worked:** a plain `_date_key_sort` (`sql: date_key`) proxy — this
   cleared `_eop_rank is not defined`.

4. **Partitioning by a joined-cube grain (`keep_only: [dates.academic_year]`)
   fails**, because the join condition is itself `{CUBE}`-based
   (`{dates.date_day} = CAST({CUBE}.date_key AS TIMESTAMP)`):

   ```text
   Compile errors:
   CUBE is not defined
   student_attendance is not defined
   ```

5. **Even with an all-plain `_eop_rank` and same-cube `keep_only`, a
   `type: count_distinct` consumer still emits `CUBE is not defined`.** We did
   not isolate the final cause before stopping — open question for you (see
   below). A `type: number` consumer wrapping a plain `sum` did compile, so the
   suspects are multi-stage `count_distinct`, or the same-cube
   `{is_chronically_absent}` / `{membership_value}` filters.

### Net takeaway

Multi-stage measures here appear to require **every** referenced member (`sql`
target, `order_by`, `grain.include`, `grain.keep_only`, `filters`) to be a
**plain local column** — no `{CUBE}`, no joined-cube refs, and no partitioning
across a `{CUBE}`-based join. Our cube reaches the date grains and the
eligibility inputs (`enrollment_status`, `is_current_academic_year`) **through
joins**, which is exactly what multi-stage seems unable to use.

## Open questions for the solutions architect

1. Is the "**no `{CUBE}` / no joined refs in any multi-stage member**"
   constraint expected? The published semi-additive recipe partitions by a
   joined `date_dim.calendar_year` over a join that also uses `{CUBE}` — how is
   that meant to compile? (Version below.)
2. Is multi-stage `type: count_distinct` supported, and what is the correct form
   (Finding 5)? Should we count `rank = 1` rows via a plain `sum` instead?
3. If joined date grains can't drive `keep_only`, is the intended pattern to
   **materialize the partition columns (academic year, month, week-start) and
   the eligibility columns onto the fact table** so the cube references only
   local columns? (That is our current leading hypothesis — option A below.)
4. Is our per-enrollment deviation (`keep_only` includes the entity) compatible
   with how `grain` is meant to be used?

## Two directions we see

- **A — Make the fact self-contained.** Add plain columns to
  `fct_student_attendance_daily` (date-part grains: academic_year, calendar
  month, school-week-start; plus eligibility: `enrollment_status` /
  `is_current_academic_year` or a precomputed `is_ca_eligible` flag), then the
  `_eop` measures reference only local columns. Keeps period-end selection
  grain-adaptive in Cube.
- **B — Keep period-end in dbt.** The `is_*_record` flags already do
  per-enrollment period-end in dbt; if multi-stage's constraints outweigh the
  benefit, stay with dbt-side selection and keep the Cube layer simple
  (accepting per-grain named measures or a different anchor mechanism that does
  not break BI tools).

## Environment / local repro

- **Cube version matters:** `grain`/`keepOnly` is **not** in 1.6.38; it is in
  **1.6.59**. `package.json` is bumped to `^1.6.59` on this branch. Cube Cloud
  builds from `package.json`, so the branch staging env must be on a
  grain-capable version too.
- `CUBEJS_TESSERACT_SQL_PLANNER=true` is required (Tesseract is preview; default
  is `false`). It is a **deployment-wide** planner swap.
- Local dev server (no Cube Cloud needed; reads real `kipptaf_marts` via ADC):

  ```bash
  cd src/cube
  CUBEJS_DEV_MODE=true \
  CUBEJS_TESSERACT_SQL_PLANNER=true \
  CUBEJS_API_SECRET=<dev-secret> \
  CUBEJS_DB_BQ_PROJECT_ID=teamster-332318 \
  CUBE_GROUP_MAP='{"<you>@apps.teamschools.org":["cube-network-admin","cube-access-student-data"]}' \
  npm run dev
  ```

  `CUBE_GROUP_MAP` is the local-only `contextToGroups` bypass (gated on
  `NODE_ENV !== "production"`). Query `/cubejs-api/v1/sql` (compile-only) or
  `/load` with an HS256 JWT signed by `CUBEJS_API_SECRET` whose payload is
  `{ "email": "<you>@apps.teamschools.org" }` (the whole payload is the
  `securityContext`). The dev server's file watcher is unreliable in Codespaces
  (inotify limits) — restart it after each model edit.

## Pointers

- Cube model: `src/cube/model/cubes/student_attendance/student_attendance.yml`
  (base + `is_*_record` dims + legacy `*_year_end`/`*_month_end`/`*_week_end`
  measures; `_location_key` / `_student_enrollment_key` plain proxy dims).
- `queryRewrite` snapshot logic: `src/cube/cube.js` (`SNAPSHOT_CUBES` /
  `SNAPSHOT_MEASURE_STEMS`).
- dbt fact + period-end windows:
  `src/dbt/kipptaf/models/marts/facts/fct_student_attendance_daily.sql`.
- Cube conventions: `src/cube/CLAUDE.md`.
