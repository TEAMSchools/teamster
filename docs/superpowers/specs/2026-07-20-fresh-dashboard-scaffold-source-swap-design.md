# FRESH Dashboard Scaffold Source-Swap — Design

- **Issue**: [#4451](https://github.com/TEAMSchools/teamster/issues/4451)
- **Date**: 2026-07-20
- **Status**: Draft — pending user review (revision 2)

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

Two places hardcode `enrollment_academic_year = 2026`, both needing a manual
edit every year regardless of the scaffold source:

- `rpt_tableau__fresh_dashboard_progress_to_goals`'s two `data_stack_*` CTEs.
- `int_tableau__finalsite_student_scaffold`'s `latest_status_calc` CTE — with a
  comment admitting why: _"hardcoding year here to ensure the correct enrollment
  academic year from FS is being used. the status_crosswalk is set to one year
  only."_ This second hardcode is upstream of the dashboard entirely (it's on
  the actuals side) but gates on the same underlying concept — see "Deriving the
  current Finalsite academic year" below.

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
- Eliminate both hardcoded `2026` occurrences by deriving "the current Finalsite
  academic year" from a single source of truth.
- Reduce the analyst's annual scaffold-maintenance burden to only the rows
  PowerSchool genuinely can't supply, with tooling to generate the boilerplate
  part of that.
- Produce a living reference doc and a maintenance skill so a future engineer or
  Ops user can operate this dashboard without reverse-engineering the SQL from
  scratch.

## Non-goals

- The goals sheet's target _values_ (`stg_google_sheets__finalsite__goals`) are
  unchanged — this project doesn't touch how targets are entered or computed,
  only the school x grade spine they're reported against.
- Historical / multi-year scaffold reporting. As the data currently stands,
  Finalsite's model has no straightforward path to historical spine data —
  **this is an open question, not solved here.** It's flagged explicitly in the
  reference doc (see "Open Questions" below) for follow-up discussion once the
  doc-writing phase starts.
- Any change to `int_tableau__finalsite_student_scaffold`'s status/goal-type
  logic, or to the Finalsite integration itself — beyond the one hardcoded year
  fix noted above, which shares the same root cause as the scaffold's hardcode
  and is fixed by the same mechanism.

## Current scaffold sheet contract

```text
academic_year   int64
region          string   -- e.g. "Newark", "Camden", "Miami", "Paterson"
schoolid        int64    -- PowerSchool school_number
school          string
grade_level     int64    -- -1 = whole-school total row, else 0-12
org             string   -- always "KTAF" (verified: constant network-wide)
school_level    string   -- ES / MS / HS, derived from grade_level
```

**Important semantic note on `grade_level = -1`**: in this sheet's convention,
`-1` means "this row summarizes the whole school, not one grade." That is a
**reporting convenience specific to this scaffold** — it is not a PowerSchool
concept. PowerSchool's own grade-level domain uses negative values for a
different, real meaning (pre-registration / pre-K context), and the two must
never be conflated. This directly shapes the seam model design below: the
PowerSchool-side builder must never synthesize a `-1` row from PowerSchool data,
regardless of what `low_grade`/`high_grade` happen to contain in any given year.
(Verified today: every current `stg_powerschool__schools.low_grade` value is
`>= 0` — no live collision exists yet — but the design treats the exclusion as a
permanent invariant, not a fact of today's data.)

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
- `academic_year` — the derived current Finalsite academic year (see below), not
  a historical year — `stg_powerschool__schools` is current-state only.

**No `grade_level = -1` row is synthesized here.** The PowerSchool builder emits
only real per-grade rows within `[low_grade, high_grade]`. The whole-school `-1`
summary row is, by design, always sourced from the sheet — see below.

### Sheet-side builder

`stg_google_sheets__finalsite__school_scaffold`, unchanged in structure, but its
**required contents change**: instead of holding a full spine, it now only needs
to hold:

1. A `grade_level = -1` (whole-school) row for **every** currently-existing
   school, every cycle (PowerSchool never supplies this row, so it must always
   come from the sheet).
2. Rows for any genuinely new grade or school PowerSchool doesn't have yet (a
   school not yet opened, or a grade a school hasn't turned on).

This is a real reduction in manual upkeep: once a school/grade is live in
PowerSchool, the analyst never re-types its per-grade rows — only the `-1` row
(a fixed, small, and mechanically generatable list) and true net-new entries.
See "Documentation & skill" below for the tooling that generates the `-1`
candidate list.

### Blend mode — simplified by the `-1` exclusion

Because the PowerSchool builder never emits a `-1` row, blend's "sheet fills
gaps absent from PowerSchool" rule already handles `-1` rows correctly with **no
special-casing**: every `-1` row's key (`schoolid, grade_level=-1`) is, by
construction, always absent from the PowerSchool builder's output, so it always
comes from the sheet. The same single rule
(`PowerSchool wins on any overlapping key; sheet fills the rest`) simultaneously
covers both the `-1` rows and genuinely new grades/schools — no separate branch
needed.

### Source-selection control

One dbt var, `finalsite_scaffold_source`, three legal values, default `blend`:

| Value             | Behavior                                                                                                                                                               |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `gsheet`          | Sheet builder only. Early-cycle / fallback if PowerSchool data looks wrong.                                                                                            |
| `powerschool`     | PowerSchool builder only. Note: this mode alone can never produce `-1` rows — combine with sheet data downstream if used standalone.                                   |
| `blend` (default) | PowerSchool builder, **plus** sheet rows whose `(schoolid, grade_level)` key is absent from the PowerSchool builder's output. PowerSchool wins on any overlapping key. |

The var lives in `kipptaf/dbt_project.yml`. Switching modes is a one-line PR +
rebuild. `blend` is the sensible default — most years, nobody needs to touch the
var at all; it degrades gracefully as PowerSchool coverage improves through a
cycle.

## Deriving the current Finalsite academic year

The original design proposed a manually-set `fresh_recruitment_academic_year`
var. **That's replaced** by deriving the value instead, based on a real
constraint in how Finalsite data works:

Finalsite can carry **two concurrent academic years of live student data at
once** during a transition period — not every student rolls over to the new year
at the same time, and the rollover cadence **varies by region and cannot be
standardized**. So "which year has the most/newest raw data" is not a reliable
signal for "which year is the currently valid one."

What _is_ reliable: `stg_google_sheets__finalsite__status_crosswalk` (the
manually-maintained status-mapping config) holds config for **exactly one
academic year at a time** by convention — this is exactly why
`int_tableau__finalsite_student_scaffold` could get away with a hardcoded `2026`
gated by "the status_crosswalk is set to one year only." Verified today: the
table holds exactly one row-set, `file_year = 2026`.

**New tiny model**: `int_finalsite__current_academic_year` —
`models/finalsite/intermediate/`, single row:

```sql
select max(file_year) as academic_year
from {{ ref("stg_google_sheets__finalsite__status_crosswalk") }}
```

Every model that previously hardcoded `2026` instead does
`cross join {{ ref("int_finalsite__current_academic_year") }} as cy` and
filters/derives against `cy.academic_year` (a `CROSS JOIN` on a single-row
model, not a scalar subquery, per this repo's SQL conventions). This fixes
**both** hardcode sites in one mechanism:

- `int_tableau__finalsite_student_scaffold`'s `latest_status_calc` CTE.
- `rpt_tableau__fresh_dashboard_progress_to_goals`'s two `data_stack_*` CTEs.
- The new seam model's PowerSchool-side builder also cross-joins this for its
  `academic_year` column, so the whole stack shares one source of truth for "the
  current cycle."

No separate manually-set var remains for this purpose.

## Known data model caveats (for the reference doc & skill)

These are permanent properties of how Finalsite works, not defects to fix — they
explain real, recurring sources of count discrepancy between raw Finalsite
numbers and the dashboard, and must be documented and referenced by the skill's
troubleshooting section:

- **Concurrent academic years, non-standardized rollover.** As above — two years
  of live student data can coexist, and individual students/regions roll over on
  their own uncoordinated timeline.
- **Status dates are mutable and student-scoped, not year-scoped.** A status
  date (`status_start_date` etc.) is tied to the student record, not to "the
  currently valid academic year." These dates can be **overwritten** when
  someone edits/clicks the status in the Finalsite UI — they are not an
  immutable audit trail.
- **`detailed_status_ranking` is a best-assumption ordering, not an enforced
  one.** `status_crosswalk`'s ranking encodes the _typical_
  recruitment→enrollment sequence, but real students can skip steps or move
  backward through it. Anything built assuming strict monotonic progression
  through statuses can be wrong for some students.
- Comparing `status_crosswalk` against the raw Finalsite staging data
  (`stg_finalsite__status_report`) is the standard first troubleshooting move
  for a count discrepancy — the user will walk through concrete troubleshooting
  steps for this during the skill-writing phase.

## Downstream changes

- `int_google_sheets__finalsite__scaffold` → rename to
  `int_finalsite__goals_scaffold`, moved to `models/finalsite/intermediate/`
  alongside the new seam model (it now joins the seam model to goals, not a
  sheet directly); its join logic (year/region/schoolid/grade_level) is
  unchanged.
- `rpt_tableau__fresh_dashboard_progress_to_goals` → `scaffold` CTE repoints
  from `stg_google_sheets__finalsite__school_scaffold` to
  `int_finalsite__enrollment_scaffold`; both hardcoded `2026` occurrences
  replaced per "Deriving the current Finalsite academic year" above.
- `int_tableau__finalsite_student_scaffold` → its hardcoded `2026` in
  `latest_status_calc` replaced the same way. (Only this one line changes; its
  status/goal-type logic is otherwise untouched, per Non-goals.)
- `rpt_tableau__fresh_dashboard_aggregated` → no direct change (consumes the
  renamed intermediate, not the sheet).
- `models/exposures/tableau.yml` → `fresh_dashboard` exposure's `depends_on`
  list updated for the renamed/new model refs.
- `models/google/sheets/sources-external.yml` → the `school_scaffold` source
  stays (still read by the `gsheet` /`blend` builder); no removal.
- New: `int_finalsite__current_academic_year`
  (`models/finalsite/intermediate/`).

## Documentation & skill

Mirroring the `gradebook-audit` pattern established in this repo
([docs/reference/gradebook-audit-data-model.md](https://github.com/TEAMSchools/teamster/blob/main/docs/reference/gradebook-audit-data-model.md),
`.claude/skills/gradebook-audit/`):

- **`docs/reference/fresh-dashboard-data-model.md`** — living reference doc:
  full lineage, model-by-model reference, the source-swap var mechanics, the
  "Known data model caveats" section above, and an explicit "Open Questions"
  section covering historical/multi-year reporting. Nav entry added to
  `mkdocs.yml`.
- **Goal definitions** (what "Seat Target", "FDOS Target", "New Student Target",
  etc. each mean) are documented in **both** the reference doc and as
  `description:` fields on the relevant columns in
  `stg_google_sheets__finalsite__goals.yml` / the goals-pivot properties yml —
  per this repo's convention that yml is the analyst-facing documentation
  mechanism. Content to be captured during the doc-writing phase.
- **`.claude/skills/fresh-dashboard/`** — a tiered skill:
  - A plain-language section for non-engineer (Ops/Analyst) self-serve: explains
    the data flow, walks through "why does this number look wrong" (referencing
    the data model caveats above), points to the right sheet tab or model in
    plain terms. Does not touch code.
  - A technical section for an engineer touching this for the first time: full
    lineage map, swap-var mechanics, rebuild/verify/refresh recipes, links to
    the reference doc.
  - **Annual rollover checklist**, covering:
    - Reviewing/updating `stg_google_sheets__finalsite__exclude_ids` for that
      cycle's Finalsite test/fake records (already enforced in code at the
      kipptaf-level `stg_finalsite__status_report` union — this is a process
      reminder, not a code gap).
    - Adding that cycle's `status_crosswalk` config row(s).
    - Adding the scaffold sheet's `-1` rows and any genuinely new grade/school
      rows (see next bullet).
  - **`-1` candidate-row generator**: a documented helper query (run via the
    skill, e.g. through the BigQuery MCP) that lists every currently-existing
    school missing its `-1` whole-school row in the scaffold sheet, formatted
    for copy/paste. The analyst pastes these in (plus any genuinely new
    grade/school rows) and adjusts as needed; the engineer/AI side then
    **verifies the sheet change and confirms once it has propagated to prod** —
    the same rematerialize-then-verify workflow already established in this
    project's own history (see the goals-sheet value-fix earlier in issue
    discussion).

Both are detailed further in the implementation plan, not this design doc.

## Verification (to run during implementation, before cutover)

- **`schoolid` domain alignment**: confirm
  `stg_powerschool__schools.school_number` and
  `int_people__location_crosswalk.location_powerschool_school_id` cover the same
  population of real schools (accounting for Pathways exclusions and
  multi-campus `reporting_school_id` rollups) — this is the join path Finalsite
  actuals already use to resolve `schoolid`
  (`int_finalsite__status_report_unpivot`, via `assigned_school` →
  `location_name`), independent of the new seam model. The two `schoolid`
  domains must agree for the scaffold-to-actuals join in
  `rpt_tableau__fresh_dashboard_progress_to_goals` to keep working.

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
- **Does the same rollover pattern (generate candidates → analyst fills in →
  verify & confirm prod) extend to `status_crosswalk` and the goals sheet, or do
  those need a different shape of help?** The scaffold's `-1` rows have a
  mechanically generatable candidate list (school identity is known ahead of
  time); goals-sheet rows need a human-supplied _value_ no matter what, and
  `status_crosswalk` needs a new year's mapping config, which may or may not be
  sensibly copy-forward-able from the prior year. To confirm before/at the
  implementation-plan stage.

## Out of Scope (recap)

- Goals sheet target _values_ (`stg_google_sheets__finalsite__goals`).
- `int_tableau__finalsite_student_scaffold`'s status/goal-type logic (beyond the
  one shared hardcoded-year fix) and the broader Finalsite integration.
- Historical/multi-year scaffold support (see Open Questions).
