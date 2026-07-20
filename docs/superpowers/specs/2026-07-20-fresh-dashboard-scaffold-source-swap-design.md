# FRESH Dashboard Scaffold Source-Swap — Design

- **Issue**: [#4451](https://github.com/TEAMSchools/teamster/issues/4451)
- **Date**: 2026-07-20
- **Status**: Draft — pending user review

## Context

The FRESH dashboard (`kipptaf` Tableau exposure `fresh_dashboard`) reports
enrollment recruitment progress against targets, broken out by
region/school/grade. Its data model rests on two hand-maintained Google Sheets:

- `stg_google_sheets__finalsite__goals` — the numeric targets (Seat Target, New
  Student Target, FDOS Target, etc.). **Unchanged by this project.**
- `stg_google_sheets__finalsite__school_scaffold` — the school x grade spine
  (`academic_year, region, schoolid, school, grade_level, org, school_level`)
  that everything else joins against. **This is what's being replaced.**

The scaffold sheet is consumed in two places:

1. Directly, in `rpt_tableau__fresh_dashboard_progress_to_goals`'s driving
   `scaffold` CTE (left-joined to goals and to
   `int_tableau__finalsite_student_scaffold` actuals, keyed on `schoolid`).
2. Via `int_google_sheets__finalsite__scaffold` (scaffold `INNER JOIN` goals on
   year/region/schoolid/grade_level), which feeds
   `rpt_tableau__fresh_dashboard_aggregated`.

`rpt_tableau__fresh_dashboard_progress_to_goals` also hardcodes
`enrollment_academic_year = 2026` in three places (the two `data_stack_*` CTEs'
`WHERE` clauses) — meaning the dashboard needs a manual SQL edit every year
regardless of the scaffold source.

### Why the scaffold needs to be swappable, not just replaced

Early in a recruitment cycle, the target year has no PowerSchool enrollment data
yet — a school recruiting for a brand-new grade, or a school that doesn't exist
in PowerSchool yet, has nothing to derive a spine from. The manual sheet is the
only source of truth at that point. Once actuals/school-structure exist in
PowerSchool, the sheet becomes a pure manual-upkeep liability with no
source-of-truth backing and no protection against drift (this is exactly the
class of error that motivated this project — see the two-value mismatch fixed
same-day in issue discussion).

So the design needs **one source of truth once PowerSchool has the data, falling
back to the manual sheet only where PowerSchool doesn't have it yet** — not a
permanent either/or choice.

## Goals

- Replace the scaffold's single hand-maintained source with a model that prefers
  PowerSchool-native data and falls back to the sheet only for gaps.
- Make switching between "sheet only" / "PowerSchool only" / "blended" a
  one-line change (a dbt var), not a code change.
- Remove the hardcoded recruitment year; make it an explicit, one-place var.
- Produce a living reference doc and a maintenance skill so a future engineer or
  Ops user can operate this dashboard without reverse-engineering the SQL from
  scratch.

## Non-goals

- The goals sheet (`stg_google_sheets__finalsite__goals`) is unchanged.
- Historical / multi-year scaffold reporting. As the data currently stands,
  Finalsite's model has no straightforward path to historical spine data —
  **this is an open question, not solved here.** It's flagged explicitly in the
  reference doc (see "Open Questions" below) for follow-up discussion once the
  doc-writing phase starts.
- Any change to `int_tableau__finalsite_student_scaffold` (the actuals side of
  the dashboard) or to the Finalsite integration itself.

## Current scaffold sheet contract

```text
academic_year   int64
region          string   -- e.g. "Newark", "Camden", "Miami", "Paterson"
schoolid        int64    -- PowerSchool school_number
school          string
grade_level     int64    -- -1 = school-level (no grade), else 0-12
org             string   -- always "KTAF" (verified: constant network-wide)
school_level    string   -- ES / MS / HS, derived from grade_level
```

## New seam model: `int_finalsite__enrollment_scaffold`

A new intermediate model at
`models/finalsite/intermediate/int_finalsite__enrollment_scaffold.sql` (moved
out of `models/google/sheets/` and into the existing `finalsite/` domain
directory alongside `int_finalsite__enrollment_lifecycle` etc., since it's no
longer purely sheet-derived) that emits the **same contract** as the sheet
today, plus one new column:

```text
academic_year, region, schoolid, school, grade_level, org, school_level,
scaffold_source   string   -- 'powerschool' | 'gsheet', per-row lineage tag
```

`scaffold_source` is a **per-row** tag, not a mode-level constant — in `blend`
mode a given output row is tagged with whichever builder actually produced it,
so a consumer (or a debugging session) can always tell whether a specific
school/grade came from PowerSchool or from the manual sheet.

Grain / uniqueness key: `(academic_year, region, schoolid, grade_level)` —
required by this repo's convention that all intermediate models carry a
uniqueness test.

Keeping the contract identical means every downstream consumer only needs its
`ref()` repointed — no join-key or column changes ripple through
`int_google_sheets__finalsite__scaffold` or
`rpt_tableau__fresh_dashboard_progress_to_goals`.

### PowerSchool-side builder

Derives the spine from `stg_powerschool__schools`, **not** from enrollment
actuals — a school's `low_grade`/`high_grade` grade span exists whether or not
any student is currently enrolled in a given grade, which is exactly what's
needed for a grade that's actively being recruited into. (Confirmed:
`low_grade`/`high_grade` only reflects currently-taught grades — it is **not**
updated ahead of a school's planned expansion into a new grade. So a school's
first year offering a new grade still won't appear here; that case is covered by
the sheet, per the blend logic below.)

Expand each school's grade span into one row per grade
(`generate_array(low_grade, high_grade)` + `unnest`), then attach:

- `region` — `{{ extract_region("<alias>") }}` (existing macro,
  `kipptaf/macros/utils.sql`) applied to `stg_powerschool__schools`:
  `initcap(regexp_extract(_dbt_source_project, r'kipp(\w+)'))` turns
  `kippnewark`/`kippcamden`/`kippmiami`/`kipppaterson` directly into
  `Newark`/`Camden`/`Miami`/`Paterson` — matching the sheet's `region` column
  values exactly, with no join required.
- `org` — literal `'KTAF'` (verified: constant across every row of the current
  sheet; no per-region mapping exists or is needed).
- `school_level` — same grade-band `CASE` the current
  `stg_google_sheets__finalsite__school_scaffold` model already uses (`>=9` HS,
  `>=5` MS, `>=0` ES), applied to the expanded `grade_level`.
- `academic_year` — the recruitment-year var (see below), not a historical year
  — `stg_powerschool__schools` is current-state only.
- A `grade_level = -1` (school-level, no-grade) row per school, to match the
  sheet's existing convention of one school-level summary row.

### Sheet-side builder

`stg_google_sheets__finalsite__school_scaffold`, unchanged.

### Source-selection control

One dbt var, `finalsite_scaffold_source`, three legal values, default `blend`:

| Value             | Behavior                                                                                                                                                                                                                                                         |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `gsheet`          | Sheet builder only. Early-cycle / fallback if PowerSchool data looks wrong.                                                                                                                                                                                      |
| `powerschool`     | PowerSchool builder only. Once every recruited grade/school is live in PowerSchool.                                                                                                                                                                              |
| `blend` (default) | PowerSchool builder, **plus** sheet rows whose `(schoolid, grade_level)` key is absent from the PowerSchool builder's output — i.e., schools not yet in PowerSchool at all, or grades a school doesn't currently offer. PowerSchool wins on any overlapping key. |

The var lives in `kipptaf/dbt_project.yml`. Switching modes is a one-line PR +
rebuild. `blend` is the sensible default — most years, nobody needs to touch the
var at all; it degrades gracefully as PowerSchool coverage improves through a
cycle.

### Recruitment year var

Replace the hardcoded `enrollment_academic_year = 2026` (three occurrences,
`data_stack_school` and `data_stack_school_grade` CTEs in
`rpt_tableau__fresh_dashboard_progress_to_goals`) with a dedicated var,
`fresh_recruitment_academic_year` — **not** derived from
`current_academic_year`, since the recruitment target year and the in-session
school year don't always move in lockstep (e.g. still recruiting/backfilling a
year already underway). Set explicitly each cycle.

## Downstream changes

- `int_google_sheets__finalsite__scaffold` → rename to
  `int_finalsite__goals_scaffold`, moved to `models/finalsite/intermediate/`
  alongside the new seam model (it now joins the seam model to goals, not a
  sheet directly); its join logic (year/region/schoolid/grade_level) is
  unchanged.
- `rpt_tableau__fresh_dashboard_progress_to_goals` → `scaffold` CTE repoints
  from `stg_google_sheets__finalsite__school_scaffold` to
  `int_finalsite__enrollment_scaffold`; hardcoded `2026` values become
  `var('fresh_recruitment_academic_year')`.
- `rpt_tableau__fresh_dashboard_aggregated` → no direct change (consumes the
  renamed intermediate, not the sheet).
- `models/exposures/tableau.yml` → `fresh_dashboard` exposure's `depends_on`
  list updated for the renamed/new model refs.
- `models/google/sheets/sources-external.yml` → the `school_scaffold` source
  stays (still read by the `gsheet` /`blend` builder); no removal.

## Documentation & skill

Mirroring the `gradebook-audit` pattern established in this repo
([docs/reference/gradebook-audit-data-model.md](https://github.com/TEAMSchools/teamster/blob/main/docs/reference/gradebook-audit-data-model.md),
`.claude/skills/gradebook-audit/`):

- **`docs/reference/fresh-dashboard-data-model.md`** — living reference doc:
  full lineage, model-by-model reference, the source-swap var mechanics, and an
  explicit "Open Questions" section covering historical/multi-year reporting
  (see below). Nav entry added to `mkdocs.yml`.
- **`.claude/skills/fresh-dashboard/`** — a tiered skill:
  - A plain-language section for non-engineer (Ops/Analyst) self-serve: explains
    the data flow, walks through "why does this number look wrong", points to
    the right sheet tab or model in plain terms. Does not touch code.
  - A technical section for an engineer touching this for the first time: full
    lineage map, swap-var mechanics, rebuild/verify/refresh recipes, links to
    the reference doc.

Both are detailed further in the implementation plan, not this design doc.

## Delivery

This design covers one cohesive unit of work, but implementation may land as
more than one PR (e.g. dbt refactor first, docs/skill second) — that sequencing
is an implementation-plan decision, not a design-scope split.

## Open Questions

- **Historical / multi-year scaffold reporting.** As Finalsite's data model
  currently stands, there's no straightforward way to represent historical
  recruitment cycles in the scaffold — `stg_powerschool__schools` is
  current-state only, and the sheet has never carried prior-year rows in
  practice. This needs a dedicated discussion (with the user) during the
  documentation-writing phase; it is explicitly **not** solved by this design.
  The reference doc will carry this as a known limitation until resolved.

## Out of Scope (recap)

- Goals sheet / values (`stg_google_sheets__finalsite__goals`).
- Actuals side of the dashboard (`int_tableau__finalsite_student_scaffold` and
  the broader Finalsite integration).
- Historical/multi-year scaffold support (see Open Questions).
