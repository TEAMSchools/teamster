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

Covers the whole DIBELS dashboard suite. **Currently documented below: the
Bright Spots tracker / foundation goals retrofit (#4952)** -- benchmark-goal
work, not PM/aimline. As the other tracks land, give each its own `##` section
here rather than starting a separate skill:

- **PM/aimline migration (#3834)** -- not yet documented here. Read the issue
  directly until this section exists.
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

Reads the same student population as `rpt_tableau__dibels_dashboard` (Reading
`iready_subject`, excludes self-contained and out-of-district,
active/withdrawn/graduated enrollment), scoped to **Benchmark Composite only**
-- this tracker does not use PM data at all.

**Grain is academic_year / region / grade_level / period / population /
goal_type -- aggregate, not student-level.** A student can contribute to more
than one population row (an IEP student counts toward both All and IEP), which
is exactly why this can't be flat columns on a student-grain table -- it would
need a different join-with-membership-filter per population, which is what made
folding into the existing dashboard model awkward enough to abandon.

**Unpadded goals, not the existing padded ones.**
`stg_google_sheets__dibels_bm_goals` (feeding the existing dashboard) is a
**padded** manual-freeze snapshot. Bright Spots uses the retrofitted (unpadded)
`stg_google_sheets__dibels_foundation_goals` directly -- a separate goal source,
not a shared join.

**Population membership, at the student level**: `All` always; `IEP` when
`iep_status = 'Has IEP'` (string, confirmed via data -- NOT a boolean); `MLL`
when `lep_status` (boolean, on `int_extracts__student_enrollments_subjects`).
Fan a student's composite row out to 1-3 population rows via
`cross join unnest(array_concat(['All'], if(iep_status = 'Has IEP', ['IEP'], []), if(lep_status, ['MLL'], [])))`
-- avoids a 3-way `UNION ALL` and any subquery.

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
IEPs, and MLL is coming -- see _Open: MLL population_ below). The existing
single-value staging table already required someone to collapse each range to
one number by hand, applying a rule nobody wrote down. That rule is now written
down (below) and encoded in a generator script instead of memory.

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

## Open: MLL population

T&L wants a third population, MLL, added alongside All and IEP. Two things need
answering before touching the generator -- **don't assume either**, IEP's goal
values already turned out to genuinely differ from All's once (see the min/max
rule section -- that was a real surprise, not a guess that panned out):

1. Do MLL goal _values_ actually differ from All, or could T&L reuse the same
   numbers?
2. Has the MLL block already been added to the sheet, and what's its exact
   header text (e.g. "Students who are MLL")? `build_foundation_goals_rows.py`
   currently hardcodes detection for exactly one extra block labeled `IEP` -- it
   needs generalizing to loop over N population blocks, keyed off each block's
   actual header text, not a hardcoded second block.

The Bright Spot tier _thresholds_, by contrast, are confirmed
population-agnostic (see below) -- this open item is about the goals table only.

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
block (looks for "IEP" anywhere in the first row) -- see _Open: MLL population_
above for why this detection needs generalizing before a third block shows up.

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
