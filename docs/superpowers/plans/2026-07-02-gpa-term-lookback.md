# GPA Term Lookback Intermediate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `int_powerschool__gpa_term_lookback` — a kipptaf intermediate view
giving each current-year student-school its Y1 GPA measures as of 1, 2, and 4
weeks before the current day, read from `snapshot_powerschool__gpa_term`
validity windows.

**Architecture:** One new view in
`src/dbt/kipptaf/models/powerschool/intermediate/` reading only the snapshot.
Three as-of boundary timestamps (end of day local at `current_date − 7/14/28`)
join to snapshot validity windows
(`dbt_valid_from < boundary and dbt_valid_to >= boundary`); conditional
aggregation pivots the matches wide. Spec:
`docs/superpowers/specs/2026-07-02-gpa-term-lookback-design.md`.

**Tech Stack:** dbt (kipptaf project), BigQuery, dbt unit tests.

Issue: #4315 · PR: #4316 (draft, currently spec-only) · Branch:
`anthonygwalters/feat/claude-gpa-term-lookback` (main-repo checkout, no worktree
— Read/Edit/Bash paths are plain `/workspaces/teamster/...`).

## Global Constraints

- All work on branch `anthonygwalters/feat/claude-gpa-term-lookback`.
- SQL follows `.trunk/config/.sqlfluff` (BigQuery dialect, trailing commas in
  SELECT, single quotes, 88-char lines, ST06 column ordering).
- YAML: description on the model and every column; unquoted scalars must not
  start with a backtick or contain colon-space.
- NEVER `dbt build/run --target prod` (classifier-blocked; prod builds via
  Dagster on merge). Dev builds use
  `--target dev --defer --state target/prod --favor-state` (`--favor-state`
  because stale March dev tables shadow plain `--defer` in this developer's
  datasets).
- PII stays local: any PR comment or other external write carries aggregates or
  redacted labels only — never student-level values.
- The `is_current` filter, snapshot definition, `int_powerschool__gpa_term`, and
  `int_powerschool__gpa_term_current` are all untouched.
- Commit messages: conventional commits, ending with
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Trunk pre-commit only formats; after each commit run
  `/workspaces/teamster/.trunk/tools/trunk check --force <files>` before
  claiming lint-clean.

## Reference facts (verified 2026-07-02)

- Snapshot: `snapshot_powerschool__gpa_term` (kipptaf,
  `src/dbt/kipptaf/snapshots/powerschool.yml`), check strategy, unique key
  (`_dbt_source_relation`, `studentid`, `yearid`, `schoolid`), check cols
  `gpa_y1` (float64), `gpa_y1_unweighted` (float64), `n_failing_y1` (int64),
  `dbt_valid_to_current: '9999-12-31'`.
- Prod history (yearid 35): first capture 2025-07-30, last 2026-06-23, 323
  distinct capture dates (~daily), ~851k version rows.
- The snapshot exists in `zz_stg_kipptaf_powerschool` (3.56M rows), so dbt Cloud
  CI's defer resolves it — no staging seed needed.
- kipptaf vars: `current_academic_year: 2025`,
  `local_timezone: America/New_York`. `yearid = academic_year − 1990` (= 35
  today).
- Summer freeze: yearid-35 captures stopped 2026-06-23 (year ended). Today's
  1/2-week boundaries read frozen finals; the 4-week boundary (June 4) predates
  mid-June changes, so 4-week-vs-1-week divergence exists and is the validation
  signal. When the var bumps to 2026 in July, the model goes empty until the new
  year's first snapshot rows appear — correct current-year-only behavior, not a
  bug.

---

### Task 1: Model, properties yml, unit test (TDD)

**Files:**

- Create:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gpa_term_lookback.sql`
- Create:
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gpa_term_lookback.yml`

**Interfaces:**

- Consumes: `ref("snapshot_powerschool__gpa_term")` — columns
  `_dbt_source_relation`, `studentid`, `schoolid`, `yearid`, `gpa_y1`,
  `gpa_y1_unweighted`, `n_failing_y1`, `dbt_valid_from`, `dbt_valid_to`.
- Produces: view `int_powerschool__gpa_term_lookback`, grain
  (`_dbt_source_relation`, `studentid`, `schoolid`), columns exactly as in the
  yml below. Later tasks and the future rpt view rely on these names verbatim.

- [ ] **Step 1: Write the properties yml with the unit test (RED)**

Create
`src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gpa_term_lookback.yml`:

```yaml
models:
  - name: int_powerschool__gpa_term_lookback
    description:
      Point-in-time lookbacks over `snapshot_powerschool__gpa_term` — one row
      per student-school for the current academic year, carrying the Y1 GPA
      measures in effect at the end of the day 1, 2, and 4 weeks before the
      current day (local time). Lookbacks cross terms (the snapshot tracks the
      current-term row) but never academic years — a boundary that predates the
      year's first snapshot version returns null. Check-strategy snapshots never
      close a row when it disappears from the source, so a withdrawn student's
      lookbacks return last-known values — consumers must scope by enrollment.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - _dbt_source_relation
              - studentid
              - schoolid
          config:
            severity: error
    columns:
      - name: _dbt_source_relation
        data_type: string
        description: dbt-generated relation of the originating district model.
      - name: studentid
        data_type: int64
        description:
          The internal number and ID of the associated Students record.
      - name: schoolid
        data_type: int64
        description: The School_Number of the associated Schools record.
      - name: yearid
        data_type: int64
        description:
          PowerSchool year ID of the current academic year (academic year minus
          1990). Constant across the model; carried for join convenience.
      - name: gpa_y1_1_week_prior
        data_type: float64
        description:
          Weighted Y1 GPA in effect at the end of the day 7 days before the
          current day; null when that day predates the year's first snapshot
          version.
      - name: gpa_y1_2_week_prior
        data_type: float64
        description:
          Weighted Y1 GPA in effect at the end of the day 14 days before the
          current day; null when that day predates the year's first snapshot
          version.
      - name: gpa_y1_4_week_prior
        data_type: float64
        description:
          Weighted Y1 GPA in effect at the end of the day 28 days before the
          current day; null when that day predates the year's first snapshot
          version.
      - name: gpa_y1_unweighted_1_week_prior
        data_type: float64
        description:
          Unweighted Y1 GPA in effect at the end of the day 7 days before the
          current day; null when that day predates the year's first snapshot
          version.
      - name: gpa_y1_unweighted_2_week_prior
        data_type: float64
        description:
          Unweighted Y1 GPA in effect at the end of the day 14 days before the
          current day; null when that day predates the year's first snapshot
          version.
      - name: gpa_y1_unweighted_4_week_prior
        data_type: float64
        description:
          Unweighted Y1 GPA in effect at the end of the day 28 days before the
          current day; null when that day predates the year's first snapshot
          version.
      - name: n_failing_y1_1_week_prior
        data_type: int64
        description:
          Count of failing Y1 grades in effect at the end of the day 7 days
          before the current day; null when that day predates the year's first
          snapshot version.
      - name: n_failing_y1_2_week_prior
        data_type: int64
        description:
          Count of failing Y1 grades in effect at the end of the day 14 days
          before the current day; null when that day predates the year's first
          snapshot version.
      - name: n_failing_y1_4_week_prior
        data_type: int64
        description:
          Count of failing Y1 grades in effect at the end of the day 28 days
          before the current day; null when that day predates the year's first
          snapshot version.

unit_tests:
  - name: unit_gpa_term_lookback_as_of_boundaries
    description:
      Verifies as-of version selection at the 1/2/4-week boundaries — value
      changes between lookbacks surface distinct values per horizon, an
      intra-day change on a lookback day resolves to the end-of-day version,
      boundaries predating the first snapshot version return null, and
      prior-year rows are excluded entirely.
    model: int_powerschool__gpa_term_lookback
    overrides:
      vars:
        local_timezone: America/New_York
        current_academic_year: 2025
    given:
      - input: ref('snapshot_powerschool__gpa_term')
        format: sql
        rows: |
          /* student 1: three versions spanning all three boundaries */
          select
              'newark' as _dbt_source_relation,
              1 as studentid,
              101 as schoolid,
              35 as yearid,
              cast(3.0 as float64) as gpa_y1,
              cast(2.8 as float64) as gpa_y1_unweighted,
              2 as n_failing_y1,
              timestamp(
                  date_sub(current_date('America/New_York'), interval 40 day),
                  'America/New_York'
              ) as dbt_valid_from,
              timestamp(
                  date_sub(current_date('America/New_York'), interval 20 day),
                  'America/New_York'
              ) as dbt_valid_to
          union all
          select
              'newark',
              1,
              101,
              35,
              cast(3.2 as float64),
              cast(3.0 as float64),
              1,
              timestamp(
                  date_sub(current_date('America/New_York'), interval 20 day),
                  'America/New_York'
              ),
              timestamp(
                  date_sub(current_date('America/New_York'), interval 10 day),
                  'America/New_York'
              )
          union all
          select
              'newark',
              1,
              101,
              35,
              cast(3.5 as float64),
              cast(3.1 as float64),
              0,
              timestamp(
                  date_sub(current_date('America/New_York'), interval 10 day),
                  'America/New_York'
              ),
              timestamp('9999-12-31')
          union all
          /* student 2: version flips at noon ON the 1-week lookback day —
             end-of-day rule must pick the later version */
          select
              'newark',
              2,
              101,
              35,
              cast(2.5 as float64),
              cast(2.4 as float64),
              3,
              timestamp(
                  date_sub(current_date('America/New_York'), interval 30 day),
                  'America/New_York'
              ),
              timestamp_add(
                  timestamp(
                      date_sub(
                          current_date('America/New_York'), interval 7 day
                      ),
                      'America/New_York'
                  ),
                  interval 12 hour
              )
          union all
          select
              'newark',
              2,
              101,
              35,
              cast(2.7 as float64),
              cast(2.6 as float64),
              2,
              timestamp_add(
                  timestamp(
                      date_sub(
                          current_date('America/New_York'), interval 7 day
                      ),
                      'America/New_York'
                  ),
                  interval 12 hour
              ),
              timestamp('9999-12-31')
          union all
          /* student 3: first version only 10 days old — 2- and 4-week
             boundaries predate it and must be null */
          select
              'camden',
              3,
              202,
              35,
              cast(2.0 as float64),
              cast(1.9 as float64),
              4,
              timestamp(
                  date_sub(current_date('America/New_York'), interval 10 day),
                  'America/New_York'
              ),
              timestamp('9999-12-31')
          union all
          /* student 4: prior-year row — excluded from output */
          select
              'newark',
              4,
              101,
              34,
              cast(4.0 as float64),
              cast(4.0 as float64),
              0,
              timestamp(
                  date_sub(current_date('America/New_York'), interval 400 day),
                  'America/New_York'
              ),
              timestamp('9999-12-31')
    expect:
      rows:
        - {
            _dbt_source_relation: newark,
            studentid: 1,
            schoolid: 101,
            yearid: 35,
            gpa_y1_1_week_prior: 3.5,
            gpa_y1_2_week_prior: 3.2,
            gpa_y1_4_week_prior: 3.0,
            gpa_y1_unweighted_1_week_prior: 3.1,
            gpa_y1_unweighted_2_week_prior: 3.0,
            gpa_y1_unweighted_4_week_prior: 2.8,
            n_failing_y1_1_week_prior: 0,
            n_failing_y1_2_week_prior: 1,
            n_failing_y1_4_week_prior: 2,
          }
        - {
            _dbt_source_relation: newark,
            studentid: 2,
            schoolid: 101,
            yearid: 35,
            gpa_y1_1_week_prior: 2.7,
            gpa_y1_2_week_prior: 2.5,
            gpa_y1_4_week_prior: 2.5,
            gpa_y1_unweighted_1_week_prior: 2.6,
            gpa_y1_unweighted_2_week_prior: 2.4,
            gpa_y1_unweighted_4_week_prior: 2.4,
            n_failing_y1_1_week_prior: 2,
            n_failing_y1_2_week_prior: 3,
            n_failing_y1_4_week_prior: 3,
          }
        - {
            _dbt_source_relation: camden,
            studentid: 3,
            schoolid: 202,
            yearid: 35,
            gpa_y1_1_week_prior: 2.0,
            gpa_y1_2_week_prior: null,
            gpa_y1_4_week_prior: null,
            gpa_y1_unweighted_1_week_prior: 1.9,
            gpa_y1_unweighted_2_week_prior: null,
            gpa_y1_unweighted_4_week_prior: null,
            n_failing_y1_1_week_prior: 4,
            n_failing_y1_2_week_prior: null,
            n_failing_y1_4_week_prior: null,
          }
```

Boundary math the fixtures encode (d = today, local): the N-week boundary is the
first instant of day `d − 7N + 1`. Student 1's versions
`[d−40, d−20) / [d−20, d−10) / [d−10, ∞)` cover the 4-week (`d−27`), 2-week
(`d−13`), and 1-week (`d−6`) boundaries respectively. Student 2's noon-`d−7`
flip precedes the `d−6` midnight boundary, so the 1-week value is the later
version. Student 3's only version starts `d−10`, after the `d−13` and `d−27`
boundaries.

- [ ] **Step 2: Run the unit test to verify it fails**

```bash
uv run dbt test --select int_powerschool__gpa_term_lookback \
    --project-dir src/dbt/kipptaf --defer --state target/prod \
    --favor-state --target dev
```

Expected: FAIL at parse — the yml names a model
(`int_powerschool__gpa_term_lookback`) that does not exist yet ("depends on a
node named ... which was not found" or "Model ... not found"). That parse error
is the RED state.

- [ ] **Step 3: Write the model SQL**

Create
`src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gpa_term_lookback.sql`:

```sql
with
    lookbacks as (
        select
            days_prior,

            /* first instant of the day AFTER (today - days_prior), local —
               i.e. the value in effect at the END of that lookback day */
            timestamp(
                date_add(
                    date_sub(
                        current_date('{{ var("local_timezone") }}'),
                        interval days_prior day
                    ),
                    interval 1 day
                ),
                '{{ var("local_timezone") }}'
            ) as as_of_boundary,
        from unnest([7, 14, 28]) as days_prior
    ),

    matched as (
        select
            gpa._dbt_source_relation,
            gpa.studentid,
            gpa.schoolid,
            gpa.yearid,
            gpa.gpa_y1,
            gpa.gpa_y1_unweighted,
            gpa.n_failing_y1,

            lb.days_prior,
        from {{ ref("snapshot_powerschool__gpa_term") }} as gpa
        inner join
            lookbacks as lb
            on gpa.dbt_valid_from < lb.as_of_boundary
            and gpa.dbt_valid_to >= lb.as_of_boundary
        where gpa.yearid = {{ var("current_academic_year") - 1990 }}
    )

select
    _dbt_source_relation,
    studentid,
    schoolid,
    yearid,

    max(if(days_prior = 7, gpa_y1, null)) as gpa_y1_1_week_prior,
    max(if(days_prior = 14, gpa_y1, null)) as gpa_y1_2_week_prior,
    max(if(days_prior = 28, gpa_y1, null)) as gpa_y1_4_week_prior,

    max(
        if(days_prior = 7, gpa_y1_unweighted, null)
    ) as gpa_y1_unweighted_1_week_prior,
    max(
        if(days_prior = 14, gpa_y1_unweighted, null)
    ) as gpa_y1_unweighted_2_week_prior,
    max(
        if(days_prior = 28, gpa_y1_unweighted, null)
    ) as gpa_y1_unweighted_4_week_prior,

    max(if(days_prior = 7, n_failing_y1, null)) as n_failing_y1_1_week_prior,
    max(if(days_prior = 14, n_failing_y1, null)) as n_failing_y1_2_week_prior,
    max(if(days_prior = 28, n_failing_y1, null)) as n_failing_y1_4_week_prior,
from matched
group by _dbt_source_relation, studentid, schoolid, yearid
```

Notes for the implementer:

- Validity windows are non-overlapping per key, so each (student, school,
  `days_prior`) matches at most one version — the `max(if())` pivot never
  aggregates across competing versions. Do NOT add `qualify`, `distinct`, or
  `dbt_utils.deduplicate`.
- No `materialized:` config — the kipptaf intermediate default (view) is
  required so `current_date` resolves at query time.
- No `order by`, no `group by all`.

- [ ] **Step 4: Run the unit test to verify it passes**

```bash
uv run dbt test --select int_powerschool__gpa_term_lookback \
    --project-dir src/dbt/kipptaf --defer --state target/prod \
    --favor-state --target dev
```

Expected: `unit_gpa_term_lookback_as_of_boundaries` PASS (1 unit test). If dbt
errors on the snapshot as a `given` input (unlikely — `format: sql` avoids
schema introspection), report back rather than restructuring.

- [ ] **Step 5: Build the model and its data tests in dev**

```bash
uv run dbt build --select int_powerschool__gpa_term_lookback \
    --project-dir src/dbt/kipptaf --defer --state target/prod \
    --favor-state --target dev
```

Expected: unit test PASS, view created in
`zz_anthonygwalters_kipptaf_powerschool`, uniqueness test PASS. (`dbt build`
runs the unit test again before materializing — that's normal.)

- [ ] **Step 6: Lint, commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
    src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gpa_term_lookback.sql \
    src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gpa_term_lookback.yml
```

Expected: no issues (fix any sqlfluff/yamllint findings before committing).

```bash
git add src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gpa_term_lookback.sql \
    src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gpa_term_lookback.yml
git commit -m "feat(powerschool): add int_powerschool__gpa_term_lookback

Refs #4315

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Prod-data validation (no code changes)

**Files:** none — BigQuery validation of the dev-built view (which reads the
PROD snapshot via `--defer`, so results are prod-data-derived).

The BigQuery MCP may be unavailable; fall back to `uv run python` with
`google.cloud.bigquery` (ADC) for SELECT-only queries.

- [ ] **Step 1: Coverage aggregates**

```sql
select
    regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as district,
    count(*) as n_rows,
    countif(gpa_y1_1_week_prior is not null) as n_1wk,
    countif(gpa_y1_2_week_prior is not null) as n_2wk,
    countif(gpa_y1_4_week_prior is not null) as n_4wk,
    countif(gpa_y1_4_week_prior != gpa_y1_1_week_prior) as n_4wk_1wk_diverge,
from `teamster-332318.zz_anthonygwalters_kipptaf_powerschool.int_powerschool__gpa_term_lookback`
group by district
```

Expected: rows for kippnewark, kippcamden, kippmiami; near-100% non-null rates
at every horizon (yearid-35 history is deep); `n_4wk_1wk_diverge > 0` (mid-June
grade changes sit between the 4-week and 1-week boundaries). Note: 1-week and
2-week values read the post-June-23 frozen finals — equality between THOSE two
horizons is expected this time of year, not a bug.

- [ ] **Step 2: Grain check against the snapshot**

```sql
select
    (
        select count(*)
        from `teamster-332318.zz_anthonygwalters_kipptaf_powerschool.int_powerschool__gpa_term_lookback`
    ) as n_model_rows,
    (
        select
            count(
                distinct concat(_dbt_source_relation, '|', studentid, '|', schoolid)
            )
        from `teamster-332318.kipptaf_powerschool.snapshot_powerschool__gpa_term`
        where
            yearid = 35
            and dbt_valid_from
            < timestamp(
                date_add(
                    date_sub(current_date('America/New_York'), interval 7 day),
                    interval 1 day
                ),
                'America/New_York'
            )
    ) as n_expected_rows
```

Expected: equal. (Keys whose FIRST version postdates the newest boundary have no
lookback row; filtering the snapshot side by `dbt_valid_from` before the 1-week
boundary reproduces the model's population exactly, because any key with a
version before that boundary matches at least the 1-week horizon — `concat` is
NULL-safe here since no key column is nullable.)

- [ ] **Step 3: Spot-check as-of correctness (local only — PII stays local)**

Pick 3 rows where `gpa_y1_4_week_prior != gpa_y1_1_week_prior`. For each, pull
that student-school's full version history:

```sql
select
    gpa_y1,
    gpa_y1_unweighted,
    n_failing_y1,
    dbt_valid_from,
    dbt_valid_to,
from `teamster-332318.kipptaf_powerschool.snapshot_powerschool__gpa_term`
where
    yearid = 35
    and studentid = {studentid}
    and schoolid = {schoolid}
    and _dbt_source_relation = '{relation}'
```

Manually verify: the version covering the end of `current_date − 28` (local)
carries the model's 4-week values, and likewise for 14 and 7. All three horizons
must verify on all three rows. Keep student-level output in the terminal /
`.claude/scratch/` only.

- [ ] **Step 4: Record results**

Write the aggregate results (Step 1 table, Step 2 counts, "3/3 spot-checks
verified") into the SDD progress ledger for Task 3's PR comment. No commit.

---

### Task 3: PR handoff

**Files:** none (PR metadata + push).

- [ ] **Step 1: Push**

```bash
git push origin anthonygwalters/feat/claude-gpa-term-lookback
```

- [ ] **Step 2: Update PR #4316 body and post validation comment**

Via `mcp__github__update_pull_request`: remove the "**Currently design-spec
only** — implementation to follow on this branch after inline spec review."
paragraph; tick the dbt properties-yml checkbox; leave the exposure checkbox
unticked with a note that the consumer rpt (and its exposure) land with the
dashboard-rebuild work. Read the body back and verify (the GitHub MCP strips
angle-bracket tokens and entity-encodes ampersands/quotes).

Via `mcp__github__add_issue_comment`: post the Task 2 aggregates (coverage
table, grain counts, spot-check tally) — aggregates only, no student-level
values. Read back and verify.

- [ ] **Step 3: Mark ready for review**

`mcp__github__update_pull_request` with `draft: false`. Then confirm both CI
surfaces: dbt Cloud via commit status
(`mcp__github__pull_request_read get_status`), Trunk/CodeQL/claude via check
runs (`get_check_runs`). dbt Cloud CI will actually build this model (kipptaf
`state:modified+`) — the snapshot resolves via the staging defer copy (verified
present in `zz_stg_kipptaf_powerschool`). After CI passes, fetch warnings with
`mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)`; warnings
unchanged from main are pre-existing.

- [ ] **Step 4: Hand off**

User reviews and squash-merges. On merge, Dagster materializes the view and the
snapshot continues on its schedule. No district or Dagster-side changes.
