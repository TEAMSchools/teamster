# Finalsite to Focus reconciliation consolidation

Design for GitHub issue
[#4481](https://github.com/TEAMSchools/teamster/issues/4481). Tracks Asana task
`1216756026346575` (kippmiami Focus extract changes).

## Summary

Consolidate all KIPP Miami finalsite-to-Focus reconciliation into the kippmiami
dbt layer so the kipptaf `rpt_focus__*` models are pure desired-state. Along the
way, fix two data problems: the `student_enrollment` feed no longer matches
Focus after enrollment ops edit `start_date` values, and the demographics /
addresses / contacts feeds send records for students who are not yet enrolled.

## Background

The four Focus SFTP feeds each have two dbt models:

- **kipptaf `rpt_focus__<feed>`** — network desired-state. Builds the record
  Focus should hold for each in-scope student from Finalsite data.
- **kippmiami `rpt_focus__<feed>`** — reads the kipptaf model via
  `source("kipptaf_extracts", ...)`, reconciles it against live Focus
  (`stg_focus__*`), and is the model the extract job actually pushes over SFTP
  (config in
  `src/teamster/code_locations/kippmiami/extracts/config/focus.yaml`).

### Layer split today

Three of the four feeds already keep reconciliation in kippmiami only:

- `rpt_focus__demographics` — kippmiami anti-joins `stg_focus__students`
  (import-once on student presence).
- `rpt_focus__addresses` — kippmiami anti-joins
  `stg_focus__students_join_address`, plus a completeness gate (#4320).
- `rpt_focus__contacts` — kippmiami anti-joins
  `stg_focus__students_join_people`, plus a name-present gate (#4320).

Only `student_enrollment` also reconciles in kipptaf: the kipptaf model reads
the `kippmiami_dlt_focus.student_enrollment` source, joins on
`(student_id, syear, start_date)`, and emits a delta (new rows plus unrecorded
exits). The kippmiami wrapper then diffs the delta against
`stg_focus__student_enrollment` a second time. Enrollment is therefore
reconciled against Focus twice.

### Problems

1. **Start-date drift breaks the enrollment match.** Enrollment ops edit the
   floored `start_date` on Focus enrollment rows after import. The enrollment
   match keys on `(student_id, syear, start_date)`, so an edited Focus row stops
   matching: the entry looks new and re-sends, and a later withdrawal never
   lands on the drifted row.
2. **The other three feeds are not enrolled-scoped.** They join
   `int_finalsite__enrollment_lifecycle` only as an existence gate, so records
   flow for any in-scope status — `accepted`, `enrollment_in_progress`,
   `assigned_school`, `enrolled`, `retained`. Only genuinely enrolled students
   should flow.

## Design

### Target architecture

| Layer                    | Role after this change                                      |
| ------------------------ | ----------------------------------------------------------- |
| kipptaf `rpt_focus__*`   | Pure desired-state. No reads of live Focus.                 |
| kippmiami `rpt_focus__*` | The only reconciliation layer, against live `stg_focus__*`. |

`student_enrollment` moves to match the pattern the other three feeds already
follow. The kipptaf enrollment model stops reading
`kippmiami_dlt_focus.student_enrollment`, removing the double reconciliation.

### kipptaf desired-state models

#### `rpt_focus__student_enrollment`

- Delete the `focus_enrollments` CTE and the delta `WHERE` clause.
- Add a current-academic-year filter to the `enrollments` CTE:
  `where school_year_start = {{ var("current_academic_year") }}`
  (`current_academic_year` is `2026` in both kipptaf and kippmiami).
- Keep the existing inclusion gate
  (`enrollment_start_date is not null and assigned_school is not null`).
- Result: one desired row per current-AY in-scope student, entry fields always
  populated, with `end_date` and the raw `drop_code` label populated when the
  student is a transfer-out. Grain becomes one row per `(student_id, syear)`.

#### `rpt_focus__demographics` and `rpt_focus__addresses`

Add `where c.status = 'enrolled'`, where `c` is the student's own
`stg_finalsite__contacts` record (already the driving table in both models).

#### `rpt_focus__contacts`

The driving contact here is the guardian (`stg_finalsite__contacts` aliased `g`,
joined on `rel.rel_id`), so the enrolled-only test must gate on the **student**,
not the guardian. Join the student's `stg_finalsite__contacts` row on
`rel.finalsite_enrollment_id` and filter its `status = 'enrolled'`.

### kippmiami reconciliation — `rpt_focus__student_enrollment`

The wrapper becomes the single reconciliation layer. It reads the desired state
(`kipptaf_extracts.rpt_focus__student_enrollment`), live Focus
(`stg_focus__student_enrollment`), and the drop-code decode
(`stg_focus__student_enrollment_codes`), and emits a `UNION ALL` of an entry
branch and an exit branch.

**Match keys.** Both entry-existence and the exit target key on
`(student_id, syear)` only — never `start_date`. This is the core fix: a
Focus-side `start_date` edit no longer breaks either branch.

Illustrative sketch (the implemented model follows the repo SQL conventions in
`src/dbt/CLAUDE.md`; column lists are elided):

```sql
with
    focus_enrollment as (
        select
            cast(student_id as string) as student_id,
            syear,
            format_date('%Y%m%d', start_date) as start_date,
            end_date,
            drop_code,
        from {{ ref("stg_focus__student_enrollment") }}
    ),

    -- entry-existence: any Focus enrollment for the student-year
    focus_year as (select distinct student_id, syear, from focus_enrollment),

    -- exit target: the open (end_date is null) Focus row per student-year, and
    -- whether it already carries a drop_code. One open row per student-year is
    -- expected and enforced by a data test (see Testing).
    focus_open as (
        select
            student_id,
            syear,
            min(start_date) as open_start_date,
            logical_or(drop_code is not null) as open_has_drop_code,
        from focus_enrollment
        where end_date is null
        group by student_id, syear
    ),

    desired as (
        select d.*, dc.short_name as drop_code_decoded,
        from {{ source("kipptaf_extracts", "rpt_focus__student_enrollment") }} as d
        left join
            {{ ref("stg_focus__student_enrollment_codes") }} as dc
            on d.drop_code = dc.title
            and dc.type = 'Drop'
    ),

    -- entry branch: student-year absent from Focus
    entries as (
        select desired.*,
        from desired
        left join focus_year as fy
            on desired.student_id = fy.student_id
            and desired.syear = fy.syear
        where fy.student_id is null
    ),

    -- exit branch: student-year present, its open row lacks a drop_code, and
    -- Finalsite now shows a withdrawal
    exits as (
        select desired.*, focus_open.open_start_date,
        from desired
        inner join focus_open
            on desired.student_id = focus_open.student_id
            and desired.syear = focus_open.syear
        where desired.end_date is not null and not focus_open.open_has_drop_code
    )

select /* entry columns, desired keys */ from entries
union all
select /* exit columns, keyed to open_start_date */ from exits
```

#### Entry branch

Emitted when the student has no Focus enrollment for the desired `syear`. Sends
the full entry row keyed to the desired (floored) `start_date`, with the decoded
`drop_code` and `end_date` included when the student enrolled and withdrew
inside the same window (a same-run enroll-and-exit). Once Focus holds the
student-year, the anti-join suppresses it — this is "import new enrollments only
once per year."

#### Exit branch

Emitted when the student's Focus enrollment for that `syear` is open
(`end_date is null`), its open row has no `drop_code` yet, and Finalsite now
shows a withdrawal (`end_date` present on the desired row). Sends a row keyed to
`(syear, open_start_date)` — the open Focus row's actual, possibly drifted,
`start_date` read straight from Focus — carrying the decoded `drop_code` and
`end_date`. `enrollment_code` is null so the entry is never overwritten;
`school_id` and `grade_id` carry the desired values (Focus translates them on
load and does not use them to match). This is "import drops using the current /
open Focus enrollment."

The two branches are mutually exclusive: `entries` requires the student-year to
be absent from Focus, `exits` requires it (via the `focus_open` inner join) to
be present.

### Behavior changes

- **`drop_code` is no longer backfilled onto an already-closed Focus
  enrollment.** Today `end_date` and `drop_code` backfill independently
  (`fa2dfbbef`), so a `drop_code` can land on a Focus row that already has an
  `end_date`. Keying the exit to the open row (`end_date is null`) means a
  closed Focus enrollment is treated as done. This matches the chosen "open
  enrollment" rule.
- **Enrollment feed is now current-academic-year only.** Prior-year and
  premature next-year enrollment rows no longer flow.
- **Demographics / addresses / contacts are enrolled-only.** Pre-enrollment
  statuses no longer flow to those three feeds.

### Edge cases and known limitations

- **Mid-year re-enrollment (same student-year).** If a student withdraws and
  re-enrolls in the same `syear`, Focus holds two rows for that student-year.
  The `(student_id, syear)` entry match treats the student-year as present and
  will not send the second entry. Finalsite carries current enrollment only, so
  this is an accepted limitation; enrollment ops handle intra-year re-entries
  manually.
- **Open enrollment in a prior year.** A student with a stale open prior-year
  Focus enrollment and a new current-AY Finalsite enrollment gets a new
  current-AY entry sent; the prior-year open row is not auto-closed by a
  current-year withdrawal signal. Prior-year hygiene stays an ops task.
- **Multiple open rows per student-year.** Treated as a Focus data-integrity
  problem and surfaced by a data test rather than silently resolved; the sketch
  picks the earliest `start_date` if it ever occurs.

## Testing

- **Enrollment unit tests (kippmiami).** Replace the current delta fixtures with
  cases covering: new entry (student-year absent); new-and-withdrawn in one run;
  existing entry with a new drop against an open row whose `start_date` drifted;
  existing entry whose open row already has a `drop_code` (suppress); existing
  entry that is already closed (suppress). Run the whole
  `test_type:unit,extracts.focus` directory after the rename, per
  `src/dbt/CLAUDE.md`.
- **Enrollment unit tests (kipptaf).** Update to assert pure desired-state
  output (no Focus diff) and the current-AY filter.
- **Status-filter tests.** Add or adjust coverage on demographics / addresses /
  contacts to confirm non-`enrolled` statuses are excluded.
- **New data test.** At most one open (`end_date is null`) Focus enrollment per
  `(student_id, syear)` on `stg_focus__student_enrollment` (warn), guarding the
  exit-branch grain assumption.
- **Local validation.** These models are district (kippmiami) and package
  (finalsite / focus); dbt Cloud CI does not exercise them. Validate with
  `uv run dbt build --select <model> --project-dir src/dbt/kippmiami --defer --state <abs prod manifest> --target dev`
  from the worktree (run `dbt deps` first).

## Documentation

Update `docs/reference/finalsite-focus-import.md` for the enrolled-only other
feeds, the current-AY enrollment scope, the open-enrollment drop matching, and
the dropped independent-backfill behavior.

## Rollout

Single PR. District-project and package models, so validation is local (not dbt
Cloud CI). After merge, prod materializes via the kippmiami automation-condition
sensor; confirm the next nightly extract produces the expected feed shapes.
