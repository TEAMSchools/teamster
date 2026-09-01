---
name: dibels-dashboard
description: >-
  Use when building or maintaining any part of the DIBELS dashboard suite -- the
  Bright Spots tracker (#4952), the PM/aimline migration (#3834), benchmark
  completion tracking (#4902), or anything touching
  stg_google_sheets__dibels_foundation_goals,
  stg_google_sheets__dibels_brightspot_goals, rpt_tableau__dibels_brightspots,
  rpt_gsheets__dibels_bm_goals_calculations, int_amplify__all_assessments, or
  rpt_tableau__dibels_dashboard and their lineage.
---

# DIBELS Dashboard

Covers the whole DIBELS dashboard suite. Documented below: the Bright Spots
tracker / foundation goals retrofit (#4952) -- benchmark-goal work, not
PM/aimline -- and the PM/aimline migration (#3834). As the other tracks land,
give each its own `##` section here rather than starting a separate skill:

- **Benchmark completion tracking (#4902)** -- not yet documented here.

## Bright Spots tracker / foundation goals (#4952)

Builds on the benchmark path, not PM/aimline -- the two tracks are unblocked and
separate. Full spec: issue #4952.

**Architecture, settled after three reversals mid-build:** Bright Spots is its
own standalone report, `rpt_tableau__dibels_brightspots` -- NOT folded into the
existing `rpt_tableau__dibels_dashboard`, and NOT split into a separate `int_`
feeding a passthrough `rpt_`. An earlier pass tried fitting it into the existing
dashboard model (school/region aggregates joined onto its student-grain rows,
the way `n_admin_season_school_gl_at_above` already works there via
`stg_google_sheets__dibels_bm_goals`); the next pass split the aggregate logic
into its own `int_amplify__dibels_brightspot_status` with a thin `rpt_` wrapper
selecting straight through it. That wrapper did zero transformation, which
defeats the point of the intermediate/report split (the convention exists to
buffer external consumers from internal schema evolution -- a bare passthrough
buys nothing over just consuming the `int_` directly, and reads as accidental
indirection to a reviewer). Landed on one model doing all the work, named `rpt_`
since Tableau reads it directly. If a real second consumer or a real
transformation shows up later, split it back out then -- not preemptively.

Scoped to **Benchmark Composite only** -- this tracker does not use PM data at
all.

**Grain is academic_year / region / school / grade_level / period / population /
goal_type / student_number -- student-level, not pre-aggregated.** An earlier
pass grouped straight to the
academic_year/region/grade_level/period/population/goal_type aggregate, which is
wrong for Tableau: it locks the output to exactly those cuts, with no student
row left to slice by teacher, advisory, or any demographic. Fixed by computing
the same group stats (`n_all`, `n_attained`, `attained_rate`, `gap`,
`brightspot_status`, `n_above_average_growth`, `pct_above_average_growth`) with
**window functions** (`count(...) over (partition by ...)`) instead of
`GROUP BY`, so every student keeps their own row (repeating the group's stats on
each one) plus their own `is_attained` and `is_above_average_growth` flags for
building custom cuts Tableau-side. A student can still appear more than once per
period -- once per population they belong to (an IEP student gets both an All
row and an IEP row).

**Unpadded goals, not the existing padded ones.**
`stg_google_sheets__dibels_bm_goals` (feeding the existing dashboard) is a
**padded** manual-freeze snapshot. Bright Spots uses the retrofitted (unpadded)
`stg_google_sheets__dibels_foundation_goals` directly -- a separate goal source,
not a shared join.

**Enrollment source: `int_extracts__student_enrollments`, NOT `..._subjects`.**
The `_subjects` variant is that same model cross-joined against a static 2-row
list (`Reading`/`Math`) plus a few subject-crosswalk columns
(`illuminate_subject_area`, `fast_subject`, `powerschool_credittype`, none of
which this tracker uses) -- using it means fanning every student out 2x and then
filtering straight back down with `iready_subject = 'Reading'`, which just lands
back where the base model already was. `rpt_tableau__dibels_dashboard` does use
`_subjects` (for the subject filter), which is why it looked like the default
choice at first. **Two fields exist ONLY on `_subjects`, not the base model**:
`nj_student_tier` and `mtss_enrollment` (both computed in `_subjects`'s own
CTEs). Not used here -- if a future need brings them back, that's the trade to
make explicitly, not a reason to default back to `_subjects` for everything.

**Population membership, at the student level**: `All` always; `IEP` when
`iep_status = 'Has IEP'` (string, confirmed via data -- NOT a boolean); `MLL`
when `lep_status` (boolean, on `int_extracts__student_enrollments`). Fan a
student's composite row out to 1-3 population rows via
`cross join unnest(array_concat(['All'], if(iep_status = 'Has IEP', ['IEP'], []), if(lep_status, ['MLL'], [])))`
-- avoids a 3-way `UNION ALL` and any subquery.

**ELA teacher/course/section, joined exactly like
`rpt_tableau__dibels_dashboard` does** -- `base_powerschool__course_enrollments`
filtered to the `ELA Gr*` course-name list, `rn_course_number_year = 1`, not
dropped, section not `%SC%`. This is separate from and in addition to `advisory`
(a general homeroom/advisor field, not subject-specific) -- DIBELS is a reading
assessment, so the relevant teacher is the ELA one, not the generic advisor.
**PowerSchool-only**: null for Miami (Focus) students, same known gap the
existing dashboard already has.

**`foundation_measure_standard_level` (on `int_amplify__all_assessments`), not
`aggregated_measure_standard_level`, is the field to aggregate on.** The latter
is only a 2-way split (`At/Above` / `Below/Well Below`) used by the existing
dashboard's padded columns -- too coarse for Bright Spots, which needs
`Well Below` isolated from plain `Below` to match the Well Below goal type
exactly. `foundation_measure_standard_level` already has the right 3-way split
and was built for exactly this reconciliation (it's also what
`rpt_gsheets__dibels_bm_goals_calculations` joins on).

**Gap rounding — a real bug found by row-count sanity-checking, not guessed.**
`gap` used to round to 2 decimal places, and rows would silently vanish: Newark
AY2025 K EOY All At/Above had attained 81.72% vs a 77% goal, a gap of 4.72 --
inside neither On Track (`0` to `4`) nor Bright Spot (`>= 5`). T&L's thresholds
are written as whole numbers with no stated rule for a continuous value landing
between two adjacent boundaries. Fixed by rounding `gap` to the nearest whole
point before the tier join. Caught by comparing actual row counts against the
expected combinatorics (grades x periods x populations x goal_types) rather than
trusting a clean build -- the join was an `INNER JOIN`, so a row with no
matching tier just disappears with no error.

## Why this skill exists

T&L's source doc gives goals as **ranges** ("62 - 66%") and, starting AY2025, as
**two-or-more side-by-side population blocks** (All Students, Students with
IEPs, and MLL, whose real goal values are still outstanding -- see _MLL
population -- shipped with placeholder values_ below). The existing single-value
staging table already required someone to collapse each range to one number by
hand, applying a rule nobody wrote down. That rule is now written down (below)
and encoded in a generator script instead of memory.

## The min/max rule (verified, not guessed)

Checked grade-by-grade against `stg_google_sheets__dibels_foundation_goals` for
every Newark/Camden row across AY2024 and AY2025, zero exceptions:

- **At/Above -> the LOW end** of the range
- **Well Below -> the HIGH end** of the range
- Holds identically for MOY and EOY. The rule is **goal_type-driven, not
  period-driven** -- do not reintroduce a MOY-vs-EOY branch.

## Named ranges: the recurring trap

`sheet_range` in `sources-external.yml` points at a Google Sheets **named
range**, not a tab title -- and a spreadsheet can carry several similarly-named
ranges left over from prior schema versions. This cost real back-and-forth twice
in one build:

- The foundation goals spreadsheet has BOTH
  `src_google_sheets__dibels_foundation_goals` (single underscore -> tab
  "Foundation Goals V1", 8 cols, legacy) AND
  `src_google_sheets__dibels__foundation_goals` (double underscore -> tab
  "Foundation Goals", 12 cols, current). Pointing `sheet_range` at the wrong one
  fails with a BigQuery type-conversion error that looks like a data problem
  ("Could not convert value to integer") but is actually a wrong-range problem
  -- the columns don't line up because it's reading a different tab entirely.
- A named range can also be **row-bounded**.
  `src_google_sheets__dibels__foundation_goals` was capped at 191 rows total; a
  203-row paste silently truncated the tail (whichever region got pasted last)
  with no error at all -- the build just quietly returned fewer rows. Always ask
  for headroom past the current row count when a new named range is created, and
  if a rebuilt row count is suspiciously short, check `count(*)` per region/year
  before assuming a parsing bug.

**Verify the real named range before writing `sheet_range`, every time**:

```python
ss = svc.spreadsheets().get(spreadsheetId="<id>").execute()
titles = {s["properties"]["sheetId"]: s["properties"]["title"] for s in ss["sheets"]}
for nr in ss.get("namedRanges", []):
    print(nr["name"], "->", titles.get(nr["range"].get("sheetId")), nr["range"])
```

## New staging schema: `stg_google_sheets__dibels_foundation_goals`

Source: named range `src_google_sheets__dibels__foundation_goals` (double
underscore), tab "Foundation Goals", spreadsheet
`15u_nUWcJY5-3V2xT0ZvICkQ1nrpGuMI2LAy5UMmUbNs`.

Long grain: one row per academic_year / region / grade_level / period /
population / goal_type. **Column order below is the actual sheet's header order
-- do not reorder it to suit a script; fix the script instead** (this was gotten
wrong once already: an earlier draft dropped `Grade_Range` and reordered columns
to what seemed like a cleaner shape, which then didn't match the sheet the user
actually built. The user builds the sheet; the tooling adapts to it, not the
other way around).

| column           | type        | notes                                                                                                                                                                                                                                                                             |
| ---------------- | ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Academic_Year    | int         | fall-start convention: AY2025 = SY25-26                                                                                                                                                                                                                                           |
| Region           | string      |                                                                                                                                                                                                                                                                                   |
| Grade_Range      | string      | cosmetic 3-way label -- `K-2` / `3-5` / `6-8`, a pure function of `Grade_Level` (no judgment call, so derived in the generator, not sheet-maintained). Kept alongside `Grade_Band` for continuity with the prior schema -- the two are NOT redundant, see below                   |
| Grade_Band       | string      | `GK-5` / `G6-8` -- drives the tier lookup below. Written as a real column (not derived in SQL) because T&L can change grade groupings; default rule is `grade_level <= 5 -> GK-5`, but the value should be editable after generation, not re-derived every load                   |
| Grade_Level      | int         | K = 0                                                                                                                                                                                                                                                                             |
| Period           | string      | `MOY` / `EOY`                                                                                                                                                                                                                                                                     |
| Population       | string      | `All` / `IEP` (MLL pending, see below) -- absent (skip row) for years/grades with no goal set, never fabricated                                                                                                                                                                   |
| Grade_Goal_Type  | string      | `At/Above` / `Well Below`                                                                                                                                                                                                                                                         |
| Grade_Goal_Low   | float       | raw low bound of the range                                                                                                                                                                                                                                                        |
| Grade_Goal_High  | float       | raw high bound                                                                                                                                                                                                                                                                    |
| Grade_Goal       | float       | derived via the min/max rule above                                                                                                                                                                                                                                                |
| Grade_Range_Goal | float\|null | the K-2 band-aggregate goal, same min/max rule applied to the band row's range. Populated only for Grade_Level 0/1/2; null elsewhere. **Only the K-2 band carries this** -- there is no 3-5 or 6-8 band-aggregate row in the source tab, confirmed against both AY2024 and AY2025 |

The K-2 band row itself is not emitted as its own row -- its four ranges
collapse into `Grade_Range_Goal` and attach to the K/1/2 individual-grade rows
for that region/period/population/goal_type, mirroring how the prior
single-value schema already carried it.

## MLL population -- shipped with placeholder values, real numbers still needed

`MLL` is a live `Population` value in both
`stg_google_sheets__dibels_foundation_goals` and
`stg_google_sheets__dibels_brightspot_goals` (`accepted_values` tests updated,
`rpt_tableau__dibels_brightspots` fans MLL students out correctly). **But the
AY2025 MLL goal rows are fabricated** -- explicitly requested as a stopgap ("use
fake numbers, half of IEP") to unblock a time-sensitive demo, not derived from
any T&L source. `Grade_Goal_Low`/`Grade_Goal_High`/`Grade_Goal` for every MLL
row are half the matching IEP row's values; everything else
(region/grade/period/goal_type) is identical to that IEP row. Flagged in the
sheet-source column description too.

**Before this goes anywhere near a real stakeholder**: replace the MLL rows with
T&L's actual numbers. Don't assume they'll match the halved values, or even that
they'll be close -- IEP's real goals already turned out to genuinely differ from
All's once (see the min/max rule section), so there's no reason to expect the
fabricated MLL placeholders to land anywhere near reality.

The Bright Spot tier _thresholds_ (`stg_google_sheets__dibels_brightspot_goals`)
are confirmed population-agnostic and are NOT placeholders -- only the MLL _goal
values_ are fake.

`build_foundation_goals_rows.py` still hardcodes detection for exactly one extra
population block labeled `IEP` -- it was never generalized to parse a real MLL
block from a T&L source doc, because the MLL rows here were entered by hand
(computed placeholders), not generated from a raw sheet paste. Fix this before
there's an actual MLL source to run the generator against.

## Tier lookup table: `stg_google_sheets__dibels_brightspot_goals`

Source: named range `src_google_sheets__dibels__brightspot_goals`, tab "Bright
Spots Goals", same spreadsheet as foundation_goals.

`gap` is computed upstream as "points better than goal": `attained - goal` for
At/Above, `goal - attained` for Well Below (sign-flipped so positive is always
good). One shared boundary set then covers both goal types -- no `goal_type`
column needed here.

`Population` and `Academic_Year` are both included even though the boundary
_values_ are identical across every population and both known years today.
Confirmed from T&L's own Bright Spot Brainstorm doc: the "GK-5 Overall Goals"
and "GK-5 Sped Goals" threshold rows are byte-identical. Included anyway because
-- per the user, in these exact words -- "stakeholders change their opinions
more often than you burn tokens": cheap to add now as real columns, expensive to
retrofit as a schema change later if a population's boundaries ever do diverge.

| column           | type        | notes                                                                                                                    |
| ---------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------ |
| Academic_Year    | int         | included for the same "T&L might diverge this" reasoning as everywhere else in this feature, not because it varies today |
| Grade_Band       | string      | `GK-5` / `G6-8`                                                                                                          |
| Period           | string      | `MOY` / `EOY`                                                                                                            |
| Population       | string      | `All` / `IEP` / `MLL` -- currently identical boundary values across all three, kept as separate rows on purpose          |
| Measured_Against | string      | which period's goal the gap was computed against -- `MOY` or `EOY`. Always `EOY` for the G6-8/MOY row                    |
| Tier             | string      | `Bright Spot` / `On Track` / `In Range` / `Off Track`                                                                    |
| Gap_Min          | float\|null | inclusive lower bound in percentage points; null = unbounded below                                                       |
| Gap_Max          | float\|null | inclusive upper bound in percentage points; null = unbounded above                                                       |

Full boundary table (repeat per population; 32 rows x 3 populations = 96 total
as of this writing):

| grade_band | period | measured_against | tier        | gap_min | gap_max |
| ---------- | ------ | ---------------- | ----------- | ------- | ------- |
| GK-5       | MOY    | MOY              | Bright Spot | 5       | —       |
| GK-5       | MOY    | MOY              | On Track    | 0       | 4       |
| GK-5       | MOY    | MOY              | In Range    | -5      | -1      |
| GK-5       | MOY    | MOY              | Off Track   | —       | -6      |
| GK-5       | EOY    | EOY              | Bright Spot | 5       | —       |
| GK-5       | EOY    | EOY              | On Track    | 0       | 4       |
| GK-5       | EOY    | EOY              | In Range    | -5      | -1      |
| GK-5       | EOY    | EOY              | Off Track   | —       | -6      |
| G6-8       | EOY    | EOY              | Bright Spot | 5       | —       |
| G6-8       | EOY    | EOY              | On Track    | 0       | 4       |
| G6-8       | EOY    | EOY              | In Range    | -5      | -1      |
| G6-8       | EOY    | EOY              | Off Track   | —       | -6      |
| G6-8       | MOY    | **EOY**          | Bright Spot | 0       | —       |
| G6-8       | MOY    | **EOY**          | On Track    | -3      | -1      |
| G6-8       | MOY    | **EOY**          | In Range    | -5      | -4      |
| G6-8       | MOY    | **EOY**          | Off Track   | —       | -6      |

G6-8 MOY is measured against the **EOY** goal (middle school skips MOY PM for
test prep), not against a MOY goal -- see #4952 for why.

## Growth fields on `int_amplify__all_assessments`

T&L asked for "% of students that made above average growth" BOY-to-MOY and
MOY-to-EOY. Two rounds of verification were needed before building anything --
don't skip either check on a similar ask elsewhere in this dashboard.

**Round 1 -- does growth data exist and reach this model at all?** Yes.
`measure_semester_growth` / `measure_year_growth` (both `string`) survive the
full lineage: `stg_amplify__mclass__{sftp,api}__benchmark_student_summary` ->
union -> unpivot -> `int_amplify__all_assessments`. Confirmed grain against live
prod data:

- **BOY** row: both null (no prior period to grow from)
- **MOY** row's `measure_semester_growth` = BOY-to-MOY growth
- **EOY** row's `measure_semester_growth` = MOY-to-EOY growth
- **EOY** row's `measure_year_growth` = BOY-to-EOY (full year) -- a THIRD
  comparison nobody asked for here. Don't conflate it with MOY-to-EOY.

Values are Amplify's 5-level categorical classification (`Well Below Average` /
`Below Average` / `Average` / `Above Average` / `Well Above Average`), `'NA'` on
PM rows (this concept is Benchmark-only). Sanity-checked against a real student
(107119, Newark, AY2025): raw score climbs every period (expected -- the test
scales with grade difficulty), but the **percentile** column is what growth
actually tracks -- percentile flat/up between two periods reads `Average`+,
percentile down reads `Below Average`-. Growth tracks relative national
standing, not raw score.

**Round 2 -- "% of students above average growth" is NOT the categorical field
above.** T&L's actual ask is "above the average", i.e. compute a mean growth
number across some population and flag students who beat it -- a population
statistic, not Amplify's pre-baked norm-referenced bucket. That statistic does
not exist anywhere in the source. Building it needs:

- **A base metric**: `measure_percentile` delta between periods, or
  `measure_standard_score` delta. `measure_percentile` (float64, a point-in-time
  national-norm standing) DOES flow through to `int_amplify__all_assessments`,
  but it's a status snapshot, not a growth number -- there is no raw growth
  percentile / SGP field anywhere in the amplify source models, confirmed by
  grepping for `growth.*percentile|percentile.*growth` across the whole package
  (zero hits).
- **A reference population**: average over grade+region? grade+school?
  network-wide per grade? T&L's call, not something to guess -- put it to them
  as an explicit multiple-choice question if it comes up, don't build against an
  assumed default.

**Shipped so far**: `is_above_average_growth` (boolean) on
`int_amplify__all_assessments`, derived from the categorical field only --
`true` when `measure_semester_growth` is `Above Average` or
`Well Above Average`, `false` for
`Average`/`Below Average`/`Well Below Average`, `null` on `BOY` rows and on `PM`
rows (`measure_semester_growth` is always `'NA'` there, so the concept doesn't
apply). This satisfies "flag against Amplify's own average" -- it does NOT
satisfy "average across our own population", which is the unresolved Round 2
question above.

**BigQuery gotcha hit while adding it**: a bare `null` in one `UNION ALL` branch
and a real `BOOL` expression in a sibling branch fails with
`Column N in UNION ALL has incompatible types: BOOL, INT64` -- BigQuery infers a
bare `null` as `INT64` by default. Fix:
`cast(null as bool) as is_above_average_growth` in the branch that doesn't
compute it.

## Procedure: generate goal rows from T&L's sheet

### Step 1 -- get the sheet URL and confirm access

Ask the user for the Google Sheet URL, **with `gid=` in it** so the tab is
unambiguous -- a flat Drive read returns every tab concatenated with no tab
names or cell addresses (see `.claude/context/claude_ai_Google_Drive.md`), so
tab attribution has to come from the API, which needs the exact tab.

Try the Sheets API first:

```python
import google.auth
from googleapiclient.discovery import build

creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
svc = build("sheets", "v4", credentials=creds)
svc.spreadsheets().get(spreadsheetId="<id>").execute()  # 403 -> not shared yet
```

On a 403: tell the user to share the sheet with
`codespaces@teamster-332318.iam.gserviceaccount.com`, then retry. This is a
**different identity** from both the Drive MCP (runs as the user) and the
BigQuery MCP's service account -- being shared with one says nothing about the
others.

### Step 2 -- pull the tab's raw grid to a TSV

Match the `gid` to a tab title via `spreadsheets().get()`'s
`sheets[].properties`, then:

```python
res = svc.spreadsheets().values().get(spreadsheetId="<id>", range="<Tab Name>!A1:N40").execute()
with open("ay<year>.tsv", "w") as f:
    for row in res.get("values", []):
        f.write("\t".join(row) + "\n")
```

One TSV per academic year. The generator auto-detects whether the tab has an IEP
block (looks for "IEP" anywhere in the first row) -- see _MLL population --
shipped with placeholder values_ above for why this detection needs generalizing
before a real MLL source shows up.

### Step 3 -- run the generator

```bash
uv run python .claude/skills/dibels-dashboard/scripts/build_foundation_goals_rows.py \
    out.tsv 2024=ay2024.tsv 2025=ay2025.tsv
```

It reports rows-per-file and prints warnings for anything skipped -- an
unrecognized grade token, or a range where the parsed low bound exceeds the high
bound (a real example hit in AY2024 Newark K MOY At/Above: the source cell reads
`"37 - 4"`, plainly a transcription typo -- the row is skipped rather than
guessed at; flag it back to T&L rather than silently fixing it). Band-aggregate
rows and blank cells are skipped silently and by design, not warned on.

Do not paste anything until the warning list is empty or every warning is
explained.

### Step 4 -- user pastes into the real dbt-source sheet

`out.tsv` has no header; rows append. Column order matches the schema table
above.

### Step 5 -- rebuild and verify in dev

A Sheets external table's DDL is fixed at creation -- pasting new data into the
sheet is NOT enough by itself when the column set changed (as opposed to a pure
value edit into unchanged columns). Two commands, in order, every time:

```bash
DBT_PROFILES_DIR=.dbt uv run dbt run-operation stage_external_sources \
  --args "select: google_sheets.<source_table_name>" \
  --vars '{ext_full_refresh: true}' \
  --target dev --project-dir src/dbt/kipptaf

DBT_PROFILES_DIR=.dbt uv run dbt build --select <staging_model_name> \
  --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --project-dir src/dbt/kipptaf
```

Both are dev-schema / personal-copy operations, not classifier-blocked (see
`src/dbt/CLAUDE.md`). `stage_external_sources` SKIPs an existing table without
`ext_full_refresh: true` -- easy to miss, shows as a silent no-op rather than an
error. Then query the rebuilt `zz_<user>_kipptaf_google_sheets.<model>` table
directly to confirm row counts and spot-check values against what was pasted,
per (academic_year, region, population) or whatever the grain is -- don't trust
a green build alone as proof the data landed correctly.

### Step 6 -- audit before trusting it

Sparse IEP coverage is expected, not a bug: as of AY2025, IEP goals exist only
for Newark and Camden grades K-5 -- none for grades 6-8, none for Paterson at
all. A retrofit that shows `0` IEP rows for Paterson is correct. Cross-check row
counts by `academic_year, population` against what the source tab actually
contains before assuming a parsing bug.

## PM/aimline migration (#3834)

Full spec: issue #3834. Two distinct kinds of work live under this track -- easy
to conflate, so keep them separate:

1. **Seasonal rollover of Benchmark rows already in the sheet** -- adding
   MOY/EOY for a year that only has BOY. Pure mechanical duplication, covered
   below.
2. **Entering actual PM round rows for SY26-27** -- the new per-region PM
   schedules. As of 2026-08-31, `stg_google_sheets__dibels_expected_assessments`
   has zero `academic_year = 2026` PM rows, but it is NOT a new concept for this
   sheet -- AY2024 and AY2025 both have a full working PM scaffold already (see
   _Existing PM precedent_ below). SY26-27 entry is mechanically the same
   process, blocked on: a cohort field the sheet doesn't have yet (see the
   issue's "Scaffolds and sheets" checklist), and the round-numbering overflow
   below for Miami. Not covered by the script in this section, which is
   Benchmark-only.

### Canonical annual rollover process

- **Benchmark**: every region gets `BOY` / `MOY` / `EOY` rows in
  `stg_google_sheets__dibels_expected_assessments`, dated to match that region's
  `LIT1` / `LIT2` / `LIT3` term windows already in
  `stg_google_sheets__reporting__terms`.
- **PM**: PM rounds are matched by region and grade level from the PM round
  document the Academics/T&L team delivers for the year (e.g. the SY27 "DIBELS
  PM Rounds - All Regions" doc) -- not invented or copied from a prior year's
  dates.
- **K-2 vs 3-8, if the aimline model holds**: K-2 keeps the in-house PM goal
  calculation, which requires `PLIT` rows (see _`reporting__terms` grade bands_
  below). Grades 3-8 use Amplify's aimline-provided goal-setting calculation
  directly and never need `PLIT` rows.

**Open, ask to be taught**: how `PLIT` date ranges are actually calculated is
not documented here or in the ref doc yet -- get walked through the real
calculation before attempting a rollover that needs new `PLIT` rows for K-2.

### Sheet identity

Same workbook as the Bright Spots tabs above: spreadsheet
`15u_nUWcJY5-3V2xT0ZvICkQ1nrpGuMI2LAy5UMmUbNs`.
`stg_google_sheets__dibels_expected_assessments` reads named range
`src_google_sheets__dibels_expected_assessments` (single underscore -- no
double-underscore trap here, only one range exists for this table), tab
"Expected Assessments", 16 declared columns (`sources-external.yml` around line
98). Only 13 of those are ever populated on **Benchmark** rows --
`Assessment_Include`, `PM_Goal_Include`, `PM_Goal_Criteria` are blank on every
Benchmark row seen so far. **PM rows do populate the last two**:
`PM_Goal_Include` carries `true`/`false`/blank per measure, and
`PM_Goal_Criteria` carries `AND` for grades 3+ in most regions (see below) --
don't assume all 16 columns behave like the Benchmark rows do. The named range
is NOT row-bounded (no `startRowIndex`/`endRowIndex` in its definition), so
appending past the current last row is safe -- no truncation risk like the
foundation_goals range above.

### Benchmark seasonal rollover -- the process, since it repeats every year

**Within one academic year, a benchmark season's rows differ from another
season's ONLY in `Admin_Season`, `Test_Code`, and `Month_Round`.** Every other
column (`Region`, `Grade`, `Measure_Standard`, ...) is identical, because the
same measures get tested every round. Confirmed empirically: AY2026 had exactly
192 BOY rows (48 x 4 regions) and zero MOY/EOY when this was checked
(2026-08-31) -- T&L had entered BOY and stopped there.

Generate the missing seasons by copying the existing season's rows and swapping
those three fields -- `scripts/roll_forward_expected_assessments_season.py` does
this against the LIVE sheet (Sheets API, read-only ADC) rather than BigQuery, so
the output matches the sheet's own literal formatting byte-for-byte (e.g.
`Grade` as the string `"0"`, not an int):

```bash
uv run --with google-api-python-client --with google-auth python3 \
    .claude/skills/dibels-dashboard/scripts/roll_forward_expected_assessments_season.py \
    --spreadsheet-id 15u_nUWcJY5-3V2xT0ZvICkQ1nrpGuMI2LAy5UMmUbNs \
    --tab "Expected Assessments" \
    --academic-year 2026 \
    --source-season BOY --source-test-code LIT1 \
    --target MOY:LIT2:January \
    --target EOY:LIT3:May \
    --out out.tsv
```

**`Month_Round` is the real month for THIS year's window, not a copy-pasted
historical label.** Checked against `stg_google_sheets__reporting__terms` (the
actual per-region term dates) and against AY2024/AY2025 precedent already in the
sheet: MOY has consistently been `"January"` in recent years even though the
older AY2023 rows say `"February"` -- the district's testing calendar moved
earlier since then. **EOY is `"May"` for every region, including Miami**, even
though Miami's actual EOY window (from `reporting__terms`) starts April 26 --
the sheet has never split this into an "April" label; don't introduce one
without T&L asking for it.

**`Test_Code` mapping**: `LIT1` = BOY, `LIT2` = MOY, `LIT3` = EOY. Confirmed
against `reporting__terms`, which uses the same three codes with real date
ranges per region/year.

**No re-staging needed after pasting.** Unlike the foundation_goals column-set
changes above, a seasonal rollover only adds rows to columns that already exist
-- rebuild the staging model in dev
(`dbt build --select stg_google_sheets__dibels_expected_assessments --target dev --defer --state <prod manifest>`)
and query the rebuilt table to confirm row counts; no
`stage_external_sources --ext_full_refresh` step needed.

### Existing PM precedent -- the template for item 2, verified against real rows

`assessment_type = 'PM'` rows already exist for AY2024 (Camden, Newark only) and
AY2025 (Camden, Newark, Paterson, Miami) -- this is not a new row shape, just a
new year. Confirmed by pulling the actual rows, not just the label counts (an
earlier pass here mischaracterized these as "a handful of ad hoc Miami rows" --
wrong; they're the full K-8 scaffold for two entire prior years):

- **`Admin_Season` on PM rows is the pm_period, not a season tag**: `BOY->MOY`
  or `MOY->EOY`, matching `pm_period` on the aimline model. Never `BOY` / `MOY`
  / `EOY` bare -- those are Benchmark-only.
- **`round_number` is ONE continuous sequence per academic_year/region, spanning
  both PM seasons** -- it does NOT reset to 1 at the `MOY->EOY` boundary.
  Verified round ranges: AY2024 Camden/Newark 1-9 (4 rounds `BOY->MOY` + 5
  `MOY->EOY`); AY2025 Camden/Newark/Paterson 1-8 (4+4); AY2025 Miami 1-6 (3+3).
  **Fixed for double-digit rounds** (#3834): `round_number` used to derive from
  `right(test_code, 1)`, which reached `LIT9` in AY2024 without issue
  (single-digit), but would have silently mis-parsed `LIT10`/`LIT11` as `0`/`1`
  -- exactly what Miami's 11-round SY26-27 schedule needs. Now
  `safe_cast(regexp_extract(test_code, r'LIT(\d+)') as int)` in
  `stg_google_sheets__dibels_expected_assessments.sql` -- extracts every digit
  after `LIT` (or `PLIT`; the pattern matches the `LIT` substring wherever it
  falls), not just the last one. Verified against every `test_code` value
  actually in the sheet (LIT1-LIT9 today, all single-digit) plus literal
  `LIT10`/`LIT11`/`PLIT1`/`PLIT8` test values via BigQuery -- unchanged for
  every existing row, correct for the double-digit case once it appears.
- **`Month_Round` per round already follows a real monthly progression**, not a
  placeholder: AY2025 NJ regions ran September/October/November/December for
  rounds 1-4, then February/March/March/April for rounds 5-8. AY2025 Miami ran
  October/November/December (1-3) then February/March/April (4-6).
- **`PM_Goal_Criteria` is `AND` for Camden/Newark/Paterson (grades 3+, matching
  the issue's note that all K-8 rounds use AND this year) but is never populated
  for Miami** -- confirm with T&L whether that's deliberate before copying the
  NJ pattern for Miami's SY26-27 rows.
- **No Paterson or Miami PM data exists for AY2024** -- both regions' PM
  scaffold starts at AY2025. A rebuild that shows 0 AY2024 PM rows for either
  region is correct, not a bug.

### `reporting__terms` grade bands -- `PLIT` is K-2-only, never copy it to 3-8

`reporting__terms` PM rows can carry a `Grade Band` value (e.g. `0,1,2`) on top
of the `LIT`/`PLIT` scheme above, letting K-2, grades 3-4, and grades 5-8 each
get their own rows under the same round codes. **`PLIT` itself stays K-2-only in
the SY26-27 target model.** It exists to feed the in-house, collective-average
PM goal calculation (school-day counting for the daily-growth-rate math) -- K-2
keeps that whole pipeline, but grades 3-8 move to Amplify aimline, which
supplies per-student goals directly and has no use for `PLIT`. When generating
grade-band rows for 3-4 or 5-8, duplicate only the `LIT` rows -- never `PLIT`.
`scripts/duplicate_reporting_terms_grade_band.py` enforces this (excludes
`PLIT%` codes from what it duplicates); don't build a generator that skips that
filter.

`dim_terms.term_key` was widened to include `grade_band` (#3834) specifically
because this scenario broke `unique_dim_terms_term_key` -- two rows sharing a
`code` but differing only in `Grade Band` used to collide on the same key. No
`code` prefix is needed for a new band anymore; the hash already disambiguates
on `grade_band`.

### Two "Expected Assessments" tabs and named ranges exist in parallel

Same single-vs-double-underscore trap as foundation_goals above, on this same
spreadsheet (`15u_nUWcJY5-3V2xT0ZvICkQ1nrpGuMI2LAy5UMmUbNs`):

- **`src_google_sheets__dibels_expected_assessments`** (single underscore) ->
  tab "Expected Assessments V1" (sheetId `1270280562`, 16 columns, PascalCase
  headers). The old range -- nothing points `sheet_range` at it anymore, kept
  only as a stale historical tab.
- **`src_google_sheets__dibels__expected_assessments`** (double underscore) ->
  tab "Expected Assessments" (sheetId `1536888014`, 18 columns, snake_case
  headers, `endColumnIndex: 18` -- not row-bounded). **This is the live source
  as of #3834** -- `sources-external.yml`'s `sheet_range` was moved here,
  `stg_google_sheets__dibels_expected_assessments`'s contract widened to 18
  columns, and the `if(admin_season in (...)) as assessment_type,` derivation
  dropped in favor of the sheet-authored column. Verified in dev: staged the
  external source (`ext_full_refresh`), built the staging model, 3,588 rows,
  correct `assessment_type` / `measure_standard_level` / `round_number` values.

The cutover (`sheet_range` move + `columns:` widen + contract update + drop the
derivation) landed as one change, per the _Named ranges: the recurring trap_
convention above -- don't split a future analogous cutover into separate
commits; a `sheet_range` move with a stale `columns:` list re-triggers the "New
sheet column vs `select *` contract" failure mode from `src/dbt/CLAUDE.md`.

### `measure_standard_level` cohort split (`Below` / `Well Below`)

SY26-27 needs one Expected Assessments PM row per
`(region, grade, round, measure)` **per cohort**, not one row shared across
cohorts -- Well Below and Below students can be assigned different measures
starting this year (see _Upcoming changes_ in the ref doc). For SY25-26
(`academic_year = 2025`), which is used to validate the new model against real
historical data, T&L's PM rounds doc shows every round testing Below and Well
Below on the **identical** measures with no differentiation -- so the correct
SY25-26 fix is purely mechanical: treat every existing PM row as the `Below`
copy, and duplicate it into a second row identical in every column except
`measure_standard_level`, set to `Well Below`. Benchmark rows are untouched --
Benchmark tests all students regardless of cohort.

`scripts/duplicate_expected_assessments_measure_standard_level.py` does this,
walking the whole "Expected Assessments" tab in original row order (not just the
matched rows) so every other row -- other academic years, and every Benchmark
row including 2025's and 2026's -- passes through unchanged in its original
position. Verified against prod (V1) after running it: the resulting `Below` and
`Well Below` rows are an exact 1:1 match to V1's 2025 PM rows, and every
non-2025-PM row matches V1 byte-for-byte, confirmed by multiset diff (zero
extra, zero missing on all three checks), not just a row count.

**This never invents a measure set -- it can only ever duplicate what a region's
own rows already say.** The script has no code path that copies one region's
measures onto another, so Miami's PM rows keep whatever measures Miami actually
tests, distinct from NJ's (verified: Miami's grade 0/3/5 measure sets differ
from Newark's at every grade checked). Do not "simplify" a future rewrite of
this script by templating one region's measure list across all regions -- that
would silently overwrite real regional differences.

**This does NOT generalize past 2025 to a future year where cohorts genuinely
test different measures.** If a future PM rounds doc ever specifies different
measures per cohort within the same round, this mechanical duplication is the
wrong tool -- that needs real per-cohort row entry, not a copy-with-one-field-
changed script.

### `assessment_type` -- now sheet-authored, not derived

`stg_google_sheets__dibels_expected_assessments.sql` used to derive
`assessment_type` from `admin_season`:
`if(admin_season in ('BOY', 'MOY', 'EOY'), 'Benchmark', 'PM')`. Replaced with a
sheet-authored column (added to the "Expected Assessments" tab, next to
`subject_area`) so the Benchmark/PM classification is explicit on the sheet
instead of inferred downstream by a rule only the SQL knows. Once `sheet_range`
moves to the double-underscore range (see above), drop that `if(...)` line from
the staging model and let `select *,` pass the raw column through instead.

**Backfilled for every existing row, not just new ones** -- `assessment_type` is
used across every academic year on this tab, not only SY26-27, so
`scripts/backfill_expected_assessments_derived_columns.py` fills it for all
~3,588 rows (all years) using the exact same rule the SQL used to apply, so no
row's classification changes silently. Same script also carries the
`month_round` fix below -- run once, get both.

### Benchmark `month_round` must match `reporting__terms`, not be copied forward

`month_round` on Benchmark rows (`BOY`/`MOY`/`EOY`) had drifted from the
region's actual calendar for years, undetected: it was written as one nominal
label per season (`August`/`January`/`May`) applied network-wide, including to
Miami, whose BOY and EOY windows land in different calendar months than the NJ
regions. Confirmed against `reporting__terms`' actual `Start Date`s, both years
checked: Miami's BOY starts in September (not August); Miami's EOY starts in
April (not May); two 2023 NJ `MOY` rows were also wrong (`February`, should be
`January`). Nobody had checked `month_round` against `reporting__terms` directly
before this.

**The rule going forward**: `month_round` = the calendar month of the matching
`LIT1`/`LIT2`/`LIT3` (`BOY`/`MOY`/`EOY`) row's `Start Date` in
`reporting__terms`, **per region**, not copied from last year's label and not
shared across regions.
`scripts/fix_expected_assessments_benchmark_month_round.py` derives this lookup
and corrects every Benchmark row that disagrees, for every academic year present
-- folded into `backfill_expected_assessments_derived_columns.py` above, so a
rollover only needs to run that one script.

**Gotcha that cost a wasted first pass**: before grade-band tagging existed
(pre-2025), a PM round can share the exact same `LIT1`/`LIT2`/`LIT3` code as the
real Benchmark row for that year, with no `Grade Band` value to distinguish them
either (e.g. AY2024 Camden `LIT1` has one row named `BOY`, dated 2024-08-21, and
another named `BOY->MOY`, dated 2024-09-30 -- same code, both grade-band-blank).
Matching by code alone let a PM round's date silently overwrite the real
Benchmark date when building the lookup. Only the `Name` column (exactly
`BOY`/`MOY`/`EOY`, never `BOY->MOY` etc for a PM round) disambiguates them --
caught by diffing the proposed correction against `reporting__terms` before
trusting it, not by inspecting the matching logic in isolation. Any future
script that builds a similar `reporting__terms` lookup by code needs the same
`Name` check.

### `PLIT` boundary rule -- verified, K-2 only, one open edge case

How to pick a new `PLITn` row's `Start Date`/`End Date` was an open item for a
long time (see the ref doc). Reverse-engineered and verified against real
Camden/Newark/Paterson AY2025 `reporting__terms` data, using
`int_students__calendar_day` (network-wide, SIS-neutral -- NOT
`stg_powerschool__calendar_day`, which is PowerSchool-only and would silently
exclude Miami since it's on Focus):

- `PLITn.start` = the first **in-session** day strictly after round `n-1`'s
  `End Date`
- `PLITn.end` = the last **in-session** day strictly before round `n`'s
  `Start Date`
- `PLIT1.start` = the season's own Benchmark start date directly, NOT
  calendar-derived (it's the very first day of the season, so there's no
  "previous round" to compute from)

Matched 7 real boundaries exactly across all three NJ regions before trusting it
(`scripts/generate_sy2627_k2_lit_plit_rows.py` implements it, and caught its own
bug on the first run -- `PLIT1.start` needs the direct-copy exception above, not
the day-after-previous-round math every other `PLITn` uses).

**PD days are NOT excluded from this calculation, and shouldn't be added in.**
Checked directly: `stg_powerschool__calendar_day` has a real `type = 'PD'` code
and uses it correctly for SOME PD days (e.g. 2025-11-03, 2025-12-08 both code
`insession = 0`, `type = 'PD'`) but NOT others that landed exactly on a `PLIT`
boundary (2025-10-24, 2025-12-23, 2026-03-27 all code `insession = 1`,
`type = 'IN'`, identical to a normal day, despite being real PD days per the
human-maintained school calendar). This looked at first like a reason to build
PD-day exclusion into the boundary calculation -- but checking the actual frozen
`stg_google_sheets__dibels_pm_goals` values ruled that out: Camden round 2's
frozen `PM_Round_Days` (18) exactly matches a naive PD-day-inclusive count, so
the real historical process doesn't reliably exclude PD days either. Building
that in now would be MORE correct than precedent, not consistent with it -- a
deliberate choice to make explicitly if it's ever wanted, not something to sneak
into a boundary-generating script.

**One open edge case, not resolved**: crossing from `BOY->MOY` into `MOY->EOY`,
real AY2025 data shows the new season's first `PLIT` starting ONE DAY BEFORE the
old season's last round officially ends (Camden/Newark/Paterson `PLIT5` starts
2025-12-22; `LIT4` ends 2025-12-23) -- confirmed both days are real in-session
days, not a PD-day artifact, and confirmed via Google Sheets edit history that
the dates were never changed after entry (so it's not a stale-snapshot
explanation either). Genuinely unexplained. `PLIT` rows generated for the
SY26-27 season boundary use the same clean rule as every other transition (day
after the previous round ends) rather than replicating this unexplained 1-day
overlap -- flag those specific rows if the real reason for last year's overlap
ever surfaces.

### `pm_goal_include` scaffolding -- K-2 only, same pattern as `PLIT`

Confirmed with the user against real AY2025 data before building SY26-27 rows: a
measure that's tested in SOME rounds of a season but not all still needs a row
for EVERY round of that season, for K-2 only -- the in-house collective-average
goal calculation needs trajectory continuity across the whole season, even for
rounds where that specific measure wasn't administered. `assessment_include`
stays `null` on those rows (they're not excluded from the scaffold);
`pm_goal_include` is `false` on the rounds where the measure wasn't tested that
round, `null` (active) where it was.

Verified example: Camden/Newark/Paterson grade 0 (K), `PSF`, `BOY->MOY`, AY2025
-- rounds 1-3 have `assessment_include = null`, `pm_goal_include = null`; round
4 (PSF not tested that round) still has a row, `assessment_include = null`,
`pm_goal_include = false`.

**Grades 3-8 do NOT get this treatment.** Aimline supplies a goal per measure
per round as actually tested -- there's no collective-average trajectory to keep
continuous, so `pm_goal_include` is simply `null` on every 3-8 row, and no row
exists for a grade/measure/round combination the T&L doc doesn't list. Same
K-2-only split as `PLIT`, for the same underlying reason (the in-house goal-calc
pipeline vs. aimline).

`pm_goal_criteria = 'AND'` for every row, every grade, this year -- T&L
confirmed all K-8 rounds require meeting every tested standard, not a mix of
AND/OR rounds. Don't build round-by-round OR logic for SY26-27 on the assumption
it might vary; it doesn't this year.

`scripts/generate_sy2627_expected_assessments_rows.py` implements both the K-2
scaffolding and the 3-8 filtered generation, plus the `measure_standard_level`
cohort split (`Both` -> `Below` + `Well Below` rows, `Well Below only` per the
doc -> just the one) -- verified against the concrete PSF example above, a 3-8
cohort-filtered spot check, and zero exact-duplicate rows, before handing off.
Generated 878 rows for Newark/Paterson/Camden; verified byte-for-byte against
the live sheet after pasting (one cosmetic mismatch caught and cleared: Sheets
normalizes `false` to `FALSE` on paste -- not a data problem).

### Paterson's grade bands changed between AY2025 and AY2026 -- don't reuse last year's override

The ref doc documents Paterson's AY2025 grade bands as `3` / `5,6,7` (no grade
4, no grade 8) rather than the `3,4` / `5,6,7,8` Newark and Camden use. **That
enrollment has changed**: AY2026 Paterson has 120 grade-4 students and 60
grade-8 students (zero of either in AY2025) -- confirmed via
`int_extracts__student_enrollments`, and consistent with the SY26-27 T&L doc,
which gives Newark and Paterson one shared grid with no per-region grade-band
split. Generating AY2026 rows with the old Paterson-specific band override
(`duplicate_reporting_terms_grade_band.py`'s `--region-override` flag) produces
the WRONG bands -- check current enrollment before reusing any region's
prior-year band definition, every year, not just for Paterson.

### SY26-27 NJ rollover status

`reporting__terms` (K-2 `LIT`+`PLIT`, 3-4/5-8 `LIT`-only) and
`Expected Assessments` (full PM scaffold, all grade bands, cohort-split) are
both built and verified for Newark, Paterson, and Camden. **Miami is not done**
-- its `PLIT` structure is different (windows spanning entire breaks) and its
boundary rule and PD days are unverified; see the ref doc's open items.
