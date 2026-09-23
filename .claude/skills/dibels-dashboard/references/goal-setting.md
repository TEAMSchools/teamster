# Goal setting

Setting and pasting goals: the Bright Spots / foundation track, the PM goal-row
procedure, and how each method's goals are derived.

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
not a shared join. The dashboard never reads foundation_goals, which is why the
yearly rollover needs two separate pastes rather than one -- see _Step 7_.

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

### Step 7 -- the SECOND paste: foundation goals do not reach the dashboard

**Pasting foundation goals changes nothing the dashboard displays.** Tell the
user this before they finish, because everything about the first paste looks
complete: the external re-stages, the staging model builds green, row counts
check out, and the benchmark goals on the dashboard stay exactly as they were.

The loop runs through a human twice:

```text
stg_google_sheets__dibels_foundation_goals   <- first paste (Steps 4-6)
  -> rpt_gsheets__dibels_bm_goals_calculations   (computes the goals)
    -> PASTE INTO "BM Goals" TAB                 <- second paste, Step 7
      -> src_google_sheets__dibels__bm_goals
        -> stg_google_sheets__dibels_bm_goals
          -> rpt_tableau__dibels_dashboard       (Benchmark branch, alias `g`)
```

The dashboard's Benchmark goal columns -- `admin_goal`,
`admin_goal_grade_range`, `admin_goal_season`, and every
`n_admin_season_{school,region}_gl_*` count -- come from
`stg_google_sheets__dibels_bm_goals` alone. Nothing on the dashboard reads
`stg_google_sheets__dibels_foundation_goals`. So until the second paste lands,
the new year has Benchmark rows with null goals while the calculation model
holds the answer nobody moved.

Paste target: named range `src_google_sheets__dibels__bm_goals`, spreadsheet
`15u_nUWcJY5-3V2xT0ZvICkQ1nrpGuMI2LAy5UMmUbNs`. Source of the rows:
`rpt_gsheets__dibels_bm_goals_calculations`, which carries the current year
only. Unlike the foundation_goals paste, the column set does not change, so no
`stage_external_sources` re-stage is needed -- a value-only paste.

#### Generate only the regions prod is missing -- never regenerate one already there

**The default is additive, per region.** Ask prod what it already holds,
generate only the regions absent from it, and append. A region already in the
tab is frozen and stays frozen.

```sql
select academic_year, region, count(*) as rows_
from `teamster-332318`.kipptaf_google_sheets.stg_google_sheets__dibels_bm_goals
where academic_year = <year>
group by academic_year, region
order by region
```

Anything listed there is done. Generate the complement, not the whole year.

The reason is that **the paste is not idempotent.** Only the goal columns are
stable -- they come from the frozen foundation goals sheet. The
`n_admin_season_*` headcounts are computed from live assessment data, so the
same region regenerated a week later returns different numbers as more students
test. Regenerating a region that is already present therefore does not "refresh"
it: it silently replaces figures that were already set and reported against with
figures from a later moment, and nothing in the sheet or the warehouse records
that it happened. Regions are goal-set at different times precisely because
their testing windows close at different times, so each one's snapshot is
supposed to be taken once, when that region's window closes.

**The one exception is a defect in the calculation**, where the frozen numbers
are wrong rather than merely old. Then replace the whole academic year rather
than part of it, so every region's rows come from the same code at the same
moment. That happened on 2026-09-15: all 74 AY2026 rows were regenerated after
the `bl_wb` non-determinism fix, deliberately overriding the additive rule.
Treat a full-year replace as the thing that needs justifying, not the default.

`select * except(...)` has no bearing here -- the model emits the current year
only, so "the whole year" and "everything the model returns" are the same set.

Related caution, worth checking before assuming a region is simply missing:
**Miami has benchmark goals in the tab but no foundation goals at all.**
Foundation goals cover Camden, Newark and Paterson only, so Miami's benchmark
numbers do not come from this lineage and cannot be produced by generating them
here. A Miami row absent from the tab is not a row this procedure can add.

**Verify by year, not by row count.** A populated prior year makes the totals
look healthy:

```sql
select
    academic_year,
    count(*) as bm_rows,
    countif(admin_goal is not null) as has_admin_goal,
    countif(n_admin_season_school_gl_all is not null) as has_school_counts
from `teamster-332318`.kipptaf_tableau.rpt_tableau__dibels_dashboard
where assessment_type = 'Benchmark'
group by academic_year
order by academic_year
```

A year with `bm_rows` in the tens of thousands and `has_admin_goal` at `0` is
the missing second paste. Measured 2026-09-14: AY2026 had 119,178 Benchmark rows
at `0` goals while AY2024 and AY2025 were populated, and
`rpt_gsheets__dibels_bm_goals_calculations` held 49 unpasted AY2026 rows. AY2023
reads `0` legitimately -- it predates the goals sheet.

## Nobody sets the internal PM goals -- they are derived from the cohort

**Do not describe the internal PM goal as something T&L chose.** Verified
against `rpt_gsheets__dibels_pm_goal_setting`: it averages the BENCHMARK score
per measure across students who were Below or Well Below Benchmark on the
previous composite, and that average is the cohort's starting point. The
distance from there to the padded grade-level target is the growth owed, split
across rounds by school days.

Confirmed numerically: recomputing `starting_words` from
`int_amplify__all_assessments` matches the frozen AY2025 goals sheet on 183 of
184 grade/region/season/measure combinations, average absolute difference 0.01
words. The single mismatch is consistent with the eligible population shifting
by one enrollment change since the freeze.

**The ownership split, because it is easy to state backwards:**

| Owner | Decides                                                                                    |
| ----- | ------------------------------------------------------------------------------------------ |
| T&L   | Which rounds exist, their dates, the measures each round tests, the cohort that tests them |
| Us    | Every number -- starting point, growth owed, per-round running target                      |

That is why transcribing T&L's PM Rounds doc is load-bearing work and the goal
numbers are not: the schedule exists nowhere else, and the goals are computed.

**Two things this explains.** The freeze exists because a cohort-derived goal
moves as scores arrive and differs year to year, so a weaker cohort lowers its
own bar -- pasting into `stg_google_sheets__dibels_pm_goals` fixes the year once
set, and the goal-setting model reads `current_academic_year` only. And it is
the real reason aimline is structurally different rather than
differently-sourced: ours is one line per COHORT, Amplify's is one line per
STUDENT off their own starting score. A student can be on pace against the
cohort while off their own aimline. **Neither number is wrong and a gap between
the two methods is not a reconciliation defect.**

Two doc errors this corrected, in case they resurface: the reference page said
the calculation averaged the **composite** score (it excludes Composite and
averages each measure; the composite only gates eligibility), and it called the
column `average_starting_words` (it is `starting_words`).

## benchmark_goal is Amplify's published standard, and it can be missing

`benchmark_goal` is not ours. It is Amplify's official DIBELS grade-level
standard for a (grade, measure standard, admin), and it travels a long way:

```text
sheet: src_google_sheets__dibels__goals_long
  -> grade_level_standard, per grade / measure_standard / admin_season
stg_google_sheets__dibels_goals_long
  -> adds matching_pm_season (MOY -> BOY->MOY, EOY -> MOY->EOY) and grade_level
int_google_sheets__dibels_pm_expectations        (internal chain)
  -> g.grade_level_standard as benchmark_goal
rpt_gsheets__dibels_pm_goal_setting
  -> e.benchmark_goal + 3        <- the padding is applied HERE, once
frozen sheet -> stg_google_sheets__dibels_pm_goals
int_amplify__pm_met_criteria
  -> met_admin_benchmark_goal = score >= benchmark_goal
```

**The `matching_pm_season` mapping is the whole idea of "on pace" in three lines
of staging.** A BOY->MOY round is measured against the **MOY** standard -- the
NEXT benchmark's bar, not the one the student just sat. Do not "fix" a join that
looks off by one season; that offset is the point.

**The two chains reach `goals_long` through different column pairs, and they do
agree.** `pm_expectations` joins `e.admin_season = g.matching_pm_season`; the
by-levels gate joins `e.matching_bm_season = g.admin_season` -- one maps
forward, the other back. Verified on AY2025: 378 (year, region, grade, measure,
season) combinations compared, **zero** disagreements, and the 10 null cases
coincide on both sides. Re-run that check if `matching_bm_season` on the
by-levels sheet is ever hand-edited, because a disagreement would make the two
methods pull different benchmark goals for the same student with nothing
failing.

**A null `benchmark_goal` is correct data, and it reads as failing.** Amplify
publishes no standard for a measure at a grade where that measure is not given
-- NWF is not a grade-4 measure, WRF is not a grade-4/5 measure, ORF Accuracy is
not a Kinder measure. The blank in `goals_long` is right; the gate's LEFT join
turns it into null; and **`if(score >= null, 1, 0)` returns 0, not null**, so a
student reads as failing a bar that does not exist for them.

Two populations, and only one matters. Measured on AY2025:

| Rows                                  | Null goal     | Which                                              |
| ------------------------------------- | ------------- | -------------------------------------------------- |
| Scaffold (`pm_goal_include` non-null) | 28 of 284     | G4 NWF Letter Sounds + Decoding, Newark and Camden |
| Live rounds, internal gate            | **15 of 452** | **Miami only** -- G0 ORF Accuracy, G4-5 WRF        |
| Live rounds, by-levels gate           | **30 of 938** | the same 15, doubled across the two cohorts        |

The scaffold rows are harmless -- consumers filter `pm_goal_include is null`
anyway. The live rounds are the real exposure and they are **entirely Miami**,
whose measure progression comes from its own tab in T&L's PM Rounds doc.

Reach by surface:

| Surface                        | Null `benchmark_goal` |
| ------------------------------ | --------------------- |
| Frozen goals sheet, AY2025     | 0 of 444              |
| `int_amplify__pm_met_criteria` | 0 of 36,484           |
| By-levels gate, AY2025         | 30 of 938             |
| By-levels gate, AY2026         | 0 of 1,170            |

So the internal method never sees one, while **the aimline sibling reads the
by-levels gate directly and would**. Those students could never be classified On
Track whatever they scored. AY2026 is clean, so testing this year would not
surface it. **Handle a null `benchmark_goal` explicitly in the sibling** rather
than letting `if()` collapse it to 0, and settle with T&L whether such a student
is On Track, excluded, or a distinct state.

## The internal PM evaluation is four questions, and only one is method-specific

Useful when building or reviewing the aimline sibling, because it says exactly
how much transfers.

`int_amplify__pm_met_criteria` asks, per measure, in order:

1. Did the score reach this round's running level? (`cumulative_growth_words`)
2. Did every measure standard under the `measure_name_code` pass -- so met ORF
   requires both Fluency and Accuracy?
3. Did every skill the round tested pass? (`pm_goal_criteria`, `AND` = `min()`)
4. Was the student tested on everything the round expected?
   (`completed_test_round`)

**The model stays measure grain, so the round verdicts repeat once per
measure.** `met_pm_round_overall_criteria` and `completed_test_round_int` are
round-level answers written onto every measure row of the round. A consumer that
wants one row per student-round must aggregate first, or a student tested on 4
measures weighs 4 times (`int_topline__dibels_pm_weekly` did, #5381). Use
`min()`, not `any_value()`: on 40 AY2025 student-weeks the verdict differs
across measures, where `pm_goal_criteria` mixes `AND` with null (read as OR).
`min()` is the `AND` reading, T&L's network-wide rule from SY26-27.

And separately, never feeding that rollup: `met_admin_benchmark_goal`, which
asks "at grade level" rather than "on pace". Read it as _at grade level in this
round_, not _has reached grade level_ -- it is recomputed per round and does not
latch, so it drops back to 0 when a later score dips (AY2025: 595 student x
measure x seasons met it in an earlier round and not in a later one). That is
intended; the sibling's at-grade-level verdict is per round too.

**Only question 1 is method-specific.** Amplify supplies `aimline_status`
directly instead of us building a running target from school days. The skill
pairing, the round rollup, the participation gate and the at-grade-level verdict
are all method-agnostic -- which is why the aimline sibling is smaller than this
model rather than a parallel copy of it.

The meaning of question 1 does change, though, even where the mechanics do not:
"on pace" stops meaning "keeping up with peers who started where you did" and
starts meaning "keeping up with yourself."

**T&L's four reporting categories are those two verdicts combined, with the
at-grade-level one winning outright:**

| Label                      | Rule                                              |
| -------------------------- | ------------------------------------------------- |
| On Track & Meeting Aimline | at grade level -- regardless of what on-pace says |
| Meeting Aimline, Off-Track | on pace, not yet at grade level                   |
| Below Aimline              | neither                                           |
| Not Tested                 | the participation gate                            |

That first row is a rider from T&L's own definition -- "if a student is meeting
benchmark but not aimline, they should still be in this category" -- so it is a
priority cascade, NOT a 2x2 intersection. Getting that wrong puts a
benchmark-meeting student in Below Aimline.

## Disabling a PM test: which column, and why the goals must be rebuilt

**Tell the user this before touching anything.** Two different columns, for two
different situations, and they behave differently in the goal chain.

**One measure not tested in a round -> `pm_goal_include`.** It exists on BOTH
Expected Assessments (either range) and the frozen
`src_google_sheets__dibels__pm_goals` sheet, and the two must agree. Nothing
keeps them in sync: `int_amplify__pm_met_criteria` drives from the frozen sheet
and filters `g.pm_goal_include is null`, while the scores reaching it came
through the gate's own filter. Disagree and a round is either evaluated when it
was meant to be disabled or dropped when it was meant to count, with no error
either way.

**The whole round cancelled -> `assessment_include`.** This one is NOT on the
goals sheet, and the goal chain cannot see it:
`int_google_sheets__dibels_pm_expectations` does not project the column at all,
so `rpt_gsheets__dibels_pm_goal_setting` still counts a cancelled round's school
days into `pm_days` and still emits a goal row for it. Regenerating the sheet
does not change that — it reproduces the same goals. Downstream consumers DO
filter `assessment_include is null`, so the cancelled round vanishes from the
dashboard and the roster while the trajectory stays scaled as though it had
happened.

So a cancelled round leaves the season's goals slightly too gradual, and fixing
that is a decision, not a patch: it means teaching `pm_expectations` to project
and filter the column, which changes whether a cancelled round bounds the
season. Watch the trap when doing it — `WHERE` is evaluated before window
functions, so filtering in the same `SELECT` that computes `min_pm_round` /
`max_pm_round` silently redefines the season's first and last round (measured on
AY2025: 675 rows shifted on `min`, 1,386 on `max`). That was reverted once
already in this PR for exactly that reason. Raise it with academics rather than
deciding it as a side effect.

**Either way the goals sheet is rebuilt in full, never cell-edited.** Disabling
a measure changes `min_pm_round` / `max_pm_round` for the season, which decides
which round carries `starting_words` and which is pinned to
`benchmark_goal_padded`; every round's share of the growth is proportional to
its school days out of the season total. Removing one rescales every goal in
that season, not just its own row.

**A disable does NOT mean recalculating the goals.** Goals are frozen once per
season and never recalculated or re-pasted -- that is the point of the freeze,
and it holds even when a round is cancelled afterwards. The trajectory stays as
frozen; the disabled round simply stops being evaluated. Do not offer a re-run.

Procedure:

1. Set the right column on Expected Assessments -- `pm_goal_include` for one
   measure, `assessment_include` for the whole round -- on the internal range,
   the by-levels range, or both, matching where the test actually runs.
2. Verify the `pm_goal_include` values agree between Expected Assessments and
   the frozen PM goals sheet, row for row. Nothing keeps them in sync, and a
   mismatch silently changes which rounds are evaluated.
3. For a cancelled round, say plainly that the frozen goals still include its
   school days, and that changing that is the open academics question above.

**If a goal VALUE has to change, that is Academics' edit, not our re-run.** They
enter it directly on the Google Sheet behind
`stg_google_sheets__dibels_pm_goals`. Regenerating the sheet from
`rpt_gsheets__dibels_pm_goal_setting` to reach a corrected number is the wrong
move: the model reads `current_academic_year` only and recomputes off whatever
scores have since landed, so it would silently move every other goal in the year
as well.

## Run goal setting per region, and only for regions that have finished testing

**Regions never finish benchmark testing on the same day.** `starting_words`
averages benchmark scores, so a region whose window is still open gets goals set
on a partial cohort -- and since goals are never recalculated, there is no
second chance.

**"Running goal setting" is a SELECT, not a dbt invocation.**
`rpt_gsheets__dibels_pm_goal_setting` is a view Dagster already maintains in
`kipptaf_extracts`, and it recomputes off whatever scores have landed at read
time. What the person needs from you is a query they can run in BigQuery and
copy out of, with the ready regions in the `WHERE`:

```sql
select *
from `teamster-332318`.kipptaf_extracts.rpt_gsheets__dibels_pm_goal_setting
where
    academic_year = 2026                -- current year only; state it, do not assume
    and admin_season = 'BOY->MOY'       -- the season the finished benchmark opens
    and region in ('Newark', 'Camden')  -- only regions whose window has closed
```

Three filters, three safeguards. The season filter matters as much as the region
one -- the freeze happens twice a year, and pasting both at once sets MOY->EOY
goals off BOY scores. BOY finishing opens `BOY->MOY`; MOY finishing opens
`MOY->EOY`.

When someone asks for help setting goals, do not hand over that query first.
Check the request date against `stg_google_sheets__reporting__terms` for that
benchmark administration, put only the regions whose window has closed into the
filter, and tell the person explicitly which regions are in it, which are not,
and the date each remaining window ends.

Then tell them to come back the day AFTER each remaining administration closes,
and suggest they set themselves a calendar reminder for that date. Do not
promise to remember it.

**Prod's calculation is fanned out today, and the fix is on this branch.**
Measured on prod: `int_google_sheets__dibels_pm_expectations` holds 17,102 rows
against 1,835 distinct (9.3x) and `rpt_gsheets__dibels_pm_goal_setting` 2,700
against 300 (9x), from the ungrade-predicated `reporting__terms` join. It is not
only duplicate rows -- `cumulative_growth_words` is a running sum, so it
accumulates the duplicates, and a paste taken from prod today would freeze
nine-times-inflated targets. The already-pasted AY2024 and AY2025 rows are clean
(855 rows, 855 distinct, no value above twice its `benchmark_goal`), so this has
not reached the sheet. Do not let it: check rows-equal-distinct on the query
output before anyone copies it.
