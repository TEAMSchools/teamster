# Rollover and the expectations scaffold

Rolling the expected-assessments scaffold forward a year or a season, and every
grade-band, round-numbering and calendar rule it depends on.

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

## Canonical annual rollover process

- **Benchmark**: every region gets `BOY` / `MOY` / `EOY` rows in
  `stg_google_sheets__dibels_expected_assessments`, dated to match that region's
  `LIT1` / `LIT2` / `LIT3` term windows already in
  `stg_google_sheets__reporting__terms`.
- **PM**: PM rounds are matched by region and grade level from the PM round
  document the Academics/T&L team delivers for the year -- not invented or
  copied from a prior year's dates. The `LIT` round dates are the input the
  calendar derives `PLIT` boundaries _between_, so with no round document there
  is nothing to derive and no rows can be generated for that region.

**The Academics team labels academic years by the SPRING.** "SY26" means
SY25-26, which is `academic_year = 2025` in `reporting__terms`; the SY26-27
rollover needs the doc labeled **SY27**. This burned a full cycle here: a Drive
search turned up `1BWVR_ptVJ2MFp9D-r_9r4wtc84mlMihVSr8HmgJ9lz4` ("SY26 - KIPP NJ

- DIBELS PM Rounds + Goals"), which was read as the current doc and, finding no
  Miami in it, wrongly taken as proof no Miami rounds existed anywhere. It is
  last year's document -- confirmed by data, not by title: its `8/20 - 9/12`
  BOY, `10/27 - 10/31` PM #2 and `1/6 - 1/23` MOY match Newark AY2025 exactly,
  while AY2026 runs `8/19 - 9/11`, `10/19 - 10/23`, `1/5 - 1/22`. **Date-check
  any round doc against `reporting__terms` before trusting its title**, and
  expect a title one year ahead of the `academic_year` it describes.

Second lesson from the same mistake: a Drive search run through **ADC (the
service account) sees only what has been shared with that identity**, not the
user's Drive. An empty result is not evidence a document does not exist -- ask
for it to be shared, the way the region calendar sheets were.

- **K-2 vs 3-8, if the aimline model holds**: K-2 keeps the in-house PM goal
  calculation, which requires `PLIT` rows (see _`reporting__terms` grade bands_
  below). Grades 3-8 use Amplify's aimline-provided goal-setting calculation
  directly and never need `PLIT` rows.

The `PLIT` date calculation is no longer an open question -- see _`PLIT`
boundary rule_ below, verified against real NJ **and** Miami data.

## Sheet identity

Same workbook as the Bright Spots tabs above: spreadsheet
`15u_nUWcJY5-3V2xT0ZvICkQ1nrpGuMI2LAy5UMmUbNs`.
`stg_google_sheets__dibels_expected_assessments` reads named range
`src_google_sheets__dibels__expected_assessments` (double underscore -- see _Two
"Expected Assessments" tabs and named ranges exist in parallel_ below for the
single-vs-double-underscore trap this table DOES have, post-cutover), tab
"Expected Assessments", 18 declared columns (`sources-external.yml` around line
98). Only `assessment_include`, `pm_goal_include`, `pm_goal_criteria` (the last
three) are ever blank on **Benchmark** rows. **PM rows do populate the last
two**: `pm_goal_include` carries `true`/`false`/blank per measure, and
`pm_goal_criteria` carries `AND` for every row as of SY26-27 (see below) --
don't assume all 18 columns behave like the Benchmark rows do. The named range
is NOT row-bounded (no `startRowIndex`/`endRowIndex` in its definition), so
appending past the current last row is safe -- no truncation risk like the
foundation_goals range above.

## Benchmark seasonal rollover -- the process, since it repeats every year

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

## Existing PM precedent -- the template for item 2, verified against real rows

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

## `reporting__terms` grade bands -- `PLIT` covers EVERY band, K-8

`reporting__terms` PM rows can carry a `Grade Band` value (e.g. `0,1,2`) on top
of the `LIT`/`PLIT` scheme above, letting each band get its own rows under the
same round codes.

**This section used to say `PLIT` was K-2-only. That was wrong, and it was wrong
in the direction that silently produces no data.** The reasoning behind it was
sound but its premise expired: `PLIT` feeds the in-house collective-average goal
calculation (school-day counting for the daily-growth-rate math), and while 3-8
was on aimline alone, 3-8 needed no `PLIT`. Academics now runs the internal
method across K-8, so **every** band needs `PLIT` rows -- a band without them
gets a null `pm_round_days` and drops out of the goal calculation with no error.
The user's correction was blunt and worth remembering: _"yes, we need plit rows
for 3-8 now for reporting terms."_

When band rows were duplicated across bands for this, the copy had to carry
`PLIT` as well as `LIT`. The one-shot script that did it originally hardcoded a
`PLIT%` exclusion -- that exclusion became the wrong default, not an optional
one.

**Miami does not use the NJ bands.** Miami splits K / 1-3 / 4,5 / 6-8 per T&L's
document, not K-2 / 3,4 / 5,6,7,8. Read the bands off the doc per region, every
year -- and note that any override justification of the form "this band skips
`PLIT`" is void now that every band gets it.

`dim_terms.term_key` was widened to include `grade_band` (#3834) specifically
because this scenario broke `unique_dim_terms_term_key` -- two rows sharing a
`code` but differing only in `Grade Band` used to collide on the same key. No
`code` prefix is needed for a new band anymore; the hash already disambiguates
on `grade_band`.

## Two Expected Assessments chains ship in parallel -- one per data model

Academics runs **both** PM data models for SY26-27, so both chains are live
production paths. This is not a primary-plus-fallback arrangement and neither
one is a contingency -- do not "consolidate" them.

|                          | Internal, K-8                                                        | Combo, K-2 internal + 3-8 aimline                           |
| ------------------------ | -------------------------------------------------------------------- | ----------------------------------------------------------- |
| Named range              | `src_google_sheets__dibels_expected_assessments` (single underscore) | `src_google_sheets__dibels__expected_assessments_by_levels` |
| Tab                      | "Expected Assessments V1" (sheetId `1270280562`)                     | the by-levels range on the same spreadsheet                 |
| Shape                    | 16 columns, PascalCase headers                                       | 18 columns, snake_case headers                              |
| dbt source               | `src_google_sheets__dibels__expected_assessments`                    | `src_google_sheets__dibels__expected_assessments_by_levels` |
| Staging model            | `stg_google_sheets__dibels_expected_assessments`                     | `stg_google_sheets__dibels__expected_assessments_by_levels` |
| `assessment_type`        | derived from `admin_season` in staging SQL                           | sheet-authored                                              |
| `measure_standard_level` | absent -- rows carry no cohort                                       | present -- `Below` / `Well Below`                           |
| Generator flag           | `--single-rows`                                                      | (default)                                                   |

**For the internal chain the source `name:` and its `sheet_range` disagree on
underscores, and that is correct.** The dbt source is
`src_google_sheets__dibels__expected_assessments` (double underscore) while its
`sheet_range` points at the single-underscore named range. Do not "fix" either
to match the other -- the source name is what downstream `source()` calls
resolve, the range name is what the spreadsheet calls that region. Same
single-vs-double-underscore trap as foundation_goals above, on the same
spreadsheet (`15u_nUWcJY5-3V2xT0ZvICkQ1nrpGuMI2LAy5UMmUbNs`).

#3834 originally cut the internal chain over to the 18-column range and widened
`stg_google_sheets__dibels_expected_assessments`'s contract to match. That was
reverted once academics asked for both models: the internal chain went back to
its prod shape, and the 18-column range got its own source and staging model
instead of replacing the old one. So the V1 tab is NOT a frozen historical
snapshot -- it is the internal model's live source.

A future cutover that really does move a `sheet_range` still lands as one change
(range move + `columns:` widen + contract update + derivation drop), per the
_Named ranges: the recurring trap_ convention above -- a `sheet_range` move with
a stale `columns:` list re-triggers the "New sheet column vs `select *`
contract" failure mode from `src/dbt/CLAUDE.md`.

## `measure_standard_level` cohort split (`Below` / `Well Below`)

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

This was done once with a throwaway script, and the resulting rows are in the
sheet. It walked the whole "Expected Assessments" tab in original row order (not
just the matched rows) so every other row -- other academic years, and every
Benchmark row including 2025's and 2026's -- passed through unchanged in its
original position. Verified against prod (V1) after running it: the `Below` and
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

## `assessment_type` -- derived on the internal chain, sheet-authored on the combo chain

The two chains classify Benchmark vs PM differently, and that is deliberate:

- **Internal chain** (`stg_google_sheets__dibels_expected_assessments`) derives
  it: `if(admin_season in ('BOY', 'MOY', 'EOY'), 'Benchmark', 'PM')`. The
  16-column V1 range has no such column, so the rule stays in SQL. **Leave that
  `if(...)` line alone** -- an earlier revision of this skill told you to drop
  it once `sheet_range` moved to the 18-column range; that move was reverted
  when academics asked for both models.
- **Combo chain** (`stg_google_sheets__dibels__expected_assessments_by_levels`)
  reads it from the sheet, next to `subject_area`, so the classification is
  explicit rather than inferred downstream by a rule only the SQL knows. That
  staging model has no `assessment_type` derivation at all.

Both produce the same values for the same rows -- the sheet column was
backfilled with the exact rule the SQL applies.

**Backfilled for every existing row, not just new ones** -- `assessment_type` is
used across every academic year on this tab, not only SY26-27, so the one-shot
backfill filled it for all ~3,588 rows (all years) using that same rule, so no
row's classification changed silently. That same pass also carried the
`month_round` fix below.

## Benchmark `month_round` must match `reporting__terms`, not be copied forward

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
shared across regions. This lookup was derived and every disagreeing Benchmark
row corrected, for every academic year present, as part of the one-shot backfill
pass above.

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

## Calendar and school sources -- Miami is Focus-only from AY2026

**Never read `stg_powerschool__calendar_day` for a DIBELS date calculation.**
Use `int_students__calendar_day`, which serves PowerSchool for the NJ regions
and Focus for Miami's Focus-covered years.

The frozen PowerSchool archive still carries a **rolled-forward Miami calendar
through 2027-06-29** — it queries fine and looks plausible, but against Focus's
real AY2026 calendar it has 48 phantom in-session days: 23 in July 2026 (school
is not in session in July), 7 on Aug 3-11 (before Focus's real Aug 12 start),
and 18 on Jun 4-29 (after its real Jun 3 end). The Aug 3-11 block is the
dangerous one — it sits exactly where `PLIT1`'s start anchor and round-1
boundaries land, so Miami dates computed off the PowerSchool path come out wrong
_plausibly_ rather than visibly.

Verified before switching: the two sources are **day-for-day identical for
Camden, Newark and Paterson in both SY25-26 and SY26-27**, and for Miami in
SY25-26 (205 = 205, which also confirms the archive was frozen faithfully at
cutover, so the SY25-26 Miami verification work stands). Only Miami AY2026
diverges. `int_google_sheets__dibels_pm_expectations` and
`generate_nj_lit_plit_rows.py` were both switched with zero output change: all
44 SY26-27 `PLIT` rows regenerated byte-identical, and `pm_round_days` was
unchanged across every region and academic year.

**The schools side is NOT yet fixed, and the obvious swap makes it worse.** The
model still resolves region as `stg_powerschool__schools.schoolcity` with
`state_excludefromreporting = 0`, which yields only 2 reportable Miami rows.
`int_students__schools` is the structural analogue (PowerSchool for non-Miami,
Focus for Miami) and does give Miami 7 schools — but its Focus branch supplies
neither column: `schoolcity` and `state_excludefromreporting` are **NULL for all
7 Miami rows**, so a naive ref swap drops Miami entirely on both the
`s.schoolcity = t.region` join and the reportability filter. Doing it properly
means resolving region from `dim_regions` (join `dagster_code_location` to
`_dbt_source_project`; its `name` values — Camden / Miami / Newark / Paterson —
match `reporting__terms.region` exactly) and replacing the
`state_excludefromreporting` gate with `location_key is not null`, since the
Focus branch's inner join to `stg_google_sheets__people__locations` already
drops the non-instructional schools. Tracked as remaining Miami work.

## `PLIT` boundary rule -- verified, K-2 only, one open edge case

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
(`scripts/generate_nj_lit_plit_rows.py` implements it, and caught its own bug on
the first run -- `PLIT1.start` needs the direct-copy exception above, not the
day-after-previous-round math every other `PLITn` uses).

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

**Miami follows the same rule -- verified, and it makes NJ's overlap look like
the anomaly.** Checked all six AY2025 Miami K-2 `PLIT` rows (grade band `0,1,2`,
rounds 1-6) against Miami's real Focus calendar, restricted to the five ACTIVE
schools (`int_focus__schools.max_syear is null` -- see _Calendar and school
sources_ above; the two closed schools carry a wider untrimmed calendar that
would corrupt the boundary math). Nine of the eleven checkable boundaries match
exactly. Two do not, and neither is a rule difference:

- **`PLIT3.end` diverges and is NOT resolved.** It reads `2025-11-12`; the rule
  yields `2025-12-12`, leaving 22 in-session days in no window (5 days as
  entered vs 27 by the rule). This was initially called a month-field
  transposition -- that call was wrong to make. Miami administers state testing
  three times a year and FAST PM2 lands early-to-mid December, almost exactly
  the `2025-11-13` to `2025-12-14` hole, so a deliberate PM pause across a
  testing window fits at least as well as a typo. Miami's `LIT` rounds are only
  3 days each, so a 5-day `PLIT` is not anomalously short for them either. And
  `reporting__terms` carries **no state-testing term type for Miami at all**
  (only `LIT`, `RT`, `AR`, `SRE`), so no testing row there is not evidence none
  existed. Do not "fix" this cell on the rule's authority.
- **`PLIT6.end`** reads `2026-04-02`; the rule yields `2026-04-03`, which is
  Good Friday. Same class of holiday-marking discrepancy already documented for
  NJ above -- Focus codes the day in session, the human calendar doesn't.

Critically, **Miami's season boundary is clean**: `PLIT4` starts `2025-12-18`,
the day after `LIT3` ends `2025-12-17`, exactly as the rule predicts, with no
1-day overlap. So the NJ `PLIT5` overlap above is a three-region NJ quirk, not
network behavior -- which strengthens the decision to generate SY26-27 season
boundaries with the clean rule.

**`PLIT1.start` for Miami is neither the first in-session day nor the Benchmark
start.** AY2025 `PLIT1` starts `2025-08-12` while active Miami's first
in-session day is `2025-08-11` and its `BOY` Benchmark window is `2025-09-08` to
`2025-09-26`. For NJ the two coincide (the region's `BOY` Benchmark opens on
roughly the first day of school), so the "copy the Benchmark start" shortcut
used for NJ does NOT transfer -- Miami's Benchmark sits a month into the year.
Get `PLIT1.start` confirmed by T&L for Miami rather than deriving it.

## A round can legitimately have NO `PLIT` window -- 10 rows against 11 rounds is not a bug

SY26-27 Miami has 11 rounds but only 10 `PLIT` rows. That is correct. T&L
extended PM #2 to run `10/26` through `11/06`, and PM #3 starts `11/09`, so no
school days remain between them -- the derived `PLIT3` start (`11/09`) lands
after its derived end (`11/06`). `generate_miami_lit_plit_rows.py` skips such a
round and prints which one, rather than emitting an inverted range.

**Do not "restore" the missing row.** The two ways to force one are both worse
than omitting it: an inverted range counts zero days anyway, and a range
overlapping `LIT2` double-counts those 5 days and inflates `pm_days`, which is
the goal-math denominator.

**No days are lost, they move.** `pm_round_days` maps `LITn` and `PLITn` to the
same round, so the 5 days that used to sit in `PLIT3` now sit inside the
extended `LIT2`. Measured before and after: round 2 went 14 to 19 days, round 3
went 9 to 4, and the `BOY->MOY` season total held at 85. Because the season
total is the denominator, no other round's proportion moved.

**Nothing downstream filters on `PLIT`.** Verified with a case-sensitive
word-boundary search across `src/dbt` and `src/cube`: zero explicit `PLIT`
references. Expected Assessments never carries a `PLIT` test code either -- its
PM rows use `LIT1` through `LIT11` only -- so the `test_code = code` join to
`reporting__terms` never looks for one. `pm_rounds_agg` also attaches by
`LEFT JOIN`, so a round with zero days keeps its row instead of vanishing. Had
any model filtered `code like 'PLIT%'`, omitting the row would have silently
dropped round 3 rather than reassigning its days.

## `pm_goal_include` scaffolding -- internal-only, and aimline must FILTER it

Confirmed with the user against real AY2025 data: a measure tested in SOME
rounds of a season but not all still needs a row for EVERY round of that season
-- the in-house collective-average goal calculation needs trajectory continuity
across the whole season, even for rounds where that specific measure wasn't
administered. `assessment_include` stays `null` on those rows (they're not
excluded from the scaffold); `pm_goal_include` is `false` on the rounds where
the measure wasn't tested that round, `null` (active) where it was.

Verified example: Camden/Newark/Paterson grade 0 (K), `PSF`, `BOY->MOY`, AY2025
-- rounds 1-3 have `assessment_include = null`, `pm_goal_include = null`; round
4 (PSF not tested that round) still has a row, `assessment_include = null`,
`pm_goal_include = false`.

The scaffold belongs to the **internal method**, not to a grade band. Academics
runs internal across K-8, so every internal grade is scaffolded. Through SY25-26
it looked K-2-only because 3-8 was the only band on aimline.

**Aimline needs no scaffold, but the by-levels sheet contains one -- so filter,
don't assume.** This is a trap worth stating flatly, because it cost a bug: it
is true that aimline has no trajectory to keep continuous, and therefore true
that it has no _use_ for scaffold rows. It does NOT follow that aimline rows
carry `pm_goal_include = null`. The SY25-26 by-levels rows were generated by
duplicating the 16-column sheet's PM rows per cohort, so they carry the internal
scaffold verbatim -- measured at 321 of 790 rows per cohort, roughly one in
five. An aimline model that drops the column on the reasoning "it's structurally
null here" emits every scaffold row as a real expectation. Write
`and e.pm_goal_include is null` in the model's `where`; the column stays
unprojected, which is what "no need for `pm_goal_include` on aimline" actually
means.

The same applies to `assessment_include`: the by-levels sheet carries the same
201 soft-deleted AY2025 rows. Whichever model reads it must filter them.

`pm_goal_criteria = 'AND'` for every row, every grade, this year -- T&L
confirmed all K-8 rounds require meeting every tested standard, not a mix of
AND/OR rounds. Don't build round-by-round OR logic for SY26-27 on the assumption
it might vary; it doesn't this year.

`scripts/generate_pm_expected_assessments_rows.py` implements both the K-2
scaffolding and the 3-8 filtered generation, plus the `measure_standard_level`
cohort split (`Both` -> `Below` + `Well Below` rows, `Well Below only` per the
doc -> just the one) -- verified against the concrete PSF example above, a 3-8
cohort-filtered spot check, and zero exact-duplicate rows, before handing off.
Generated 878 rows for Newark/Paterson/Camden; verified byte-for-byte against
the live sheet after pasting (one cosmetic mismatch caught and cleared: Sheets
normalizes `false` to `FALSE` on paste -- not a data problem).

## Generating rows for both models

Both models come out of the same transcribed T&L round data, which
`scripts/generate_pm_expected_assessments_rows.py` reads from a `--rounds` TSV
(transcribed from the doc each year, not committed; columns and example rows are
in the script's docstring):

```bash
rounds=sy2627_expected_assessments.tsv

# combo: K-2 internal scaffold + 3-8 aimline -> by-levels range, 18 columns
uv run python3 \
  .claude/skills/dibels-dashboard/scripts/generate_pm_expected_assessments_rows.py \
  --academic-year 2026 --rounds "$rounds" --out /tmp/combo.tsv

# internal applied to K-8 -> V1 range, 16 columns
uv run python3 \
  .claude/skills/dibels-dashboard/scripts/generate_pm_expected_assessments_rows.py \
  --academic-year 2026 --rounds "$rounds" --single-rows --out /tmp/internal.tsv
```

`--single-rows` does two things: widens the scaffold from `K2_GRADES` to every
grade 0-8, and drops columns 6 and 7 (`assessment_type`,
`measure_standard_level`) so the output matches the 16-column V1 order.

`--no-scaffold` empties the scaffold set instead, so every grade takes the
aimline pattern -- rows only for rounds the doc lists, blank `pm_goal_include`.
Use it with the default 18-column output for aimline-across-K-8. On the SY27 doc
it yields 1,170 rows (758 NJ + 412 Miami) against the default's 1,294; the
124-row difference is exactly the K-2 scaffold-fill rows.

**Generating single rows from the doc is not lossy; collapsing existing split
rows would be.** The round data carries ONE measure list per grade/round plus a
cohort tag -- never per-cohort measure lists -- so single-row mode just omits
the tag. The reverse direction, folding already-split sheet rows down to single
rows, is a real decision and no script can infer it: of the 709 AY2026
`(region, grade, round, measure)` combos in the by-levels range, 461 carry both
cohorts and **248 carry `Well Below` only**. The same query over AY2025 returns
790 combos with both cohorts on every one and zero cohort-only, so re-derive per
year rather than reusing either number. Those 248 encode who gets tested --
Miami alternates cohorts by round, and several NJ rounds are Well-Below-only.
Flattening them either over-tests `Below` students or throws the distinction
away. Always regenerate from the doc; never collapse the sheet.

**The `pm_goal_include` scaffold is the only grade-band difference between the
models.** Under aimline, 3-8 rows carry a blank `pm_goal_include` and exist only
for rounds the doc lists -- Amplify supplies the goal, so no trajectory scaffold
is needed. The internal model gives 3-8 the same scaffold K-2 always gets: a row
for every round of a season for any measure tested at least once that season,
with `pm_goal_include = false` on the untested rounds. Measured on the sheet:
AY2025 3-8 has 504 rows at `false`; AY2026 3-8 in the combo model has 0.

**`reporting__terms` DOES need `PLIT` rows for 3-8 now.** An earlier version of
this section said it did not, reasoning that `PLIT` was K-2-only in AY2025
across all four regions (true: `0,1,2` carries `PLIT` rows, `3,4` and `5,6,7,8`
carry zero). That reasoning was wrong. `PLIT` is not a K-2 property -- it is
what the internal method counts school days against, and it was K-2-only only
because K-2 was the only band on the internal method. Now that academics runs
internal across K-8, every band needs `PLIT`.

Copying one band's `PLIT` rows to the others -- how the AY2026 rows were
produced -- is only correct while the bands share a calendar, which they do
today -- every band's `LIT` round covers the same dates, so the derived `PLIT`
windows coincide.

Watch the interaction with `int_google_sheets__dibels_pm_expectations`: its day
count groups on `(region, year, season, round)` with **no `grade_band`**, and
its `regexp_extract(code, r'LIT(\d+)')` is unanchored, so `PLIT1` reads as round
1 and its window is counted alongside `LIT1`'s. Measured on Newark AY2026: the
`LIT` window is 5 in-session days and `PLIT` adds 23/9/13/12. Since all bands
share one group, adding 3-8 `PLIT` rows is a no-op there **only** while their
dates match K-2's. If a band's `PLIT` dates ever diverge, the group unions both
windows and every band's count shifts.

**`pm_goal_criteria` stays `AND`** on every row of both models -- a T&L
requirement for the year, not an aimline artifact.

## Paterson's grade bands changed between AY2025 and AY2026 -- don't reuse last year's override

The ref doc documents Paterson's AY2025 grade bands as `3` / `5,6,7` (no grade
4, no grade 8) rather than the `3,4` / `5,6,7,8` Newark and Camden use. **That
enrollment has changed**: AY2026 Paterson has 120 grade-4 students and 60
grade-8 students (zero of either in AY2025) -- confirmed via
`int_extracts__student_enrollments`, and consistent with the SY26-27 T&L doc,
which gives Newark and Paterson one shared grid with no per-region grade-band
split. Generating AY2026 rows with the old Paterson-specific band override (the
per-region band override the old band-duplication script carried) produces the
WRONG bands -- check current enrollment before reusing any region's prior-year
band definition, every year, not just for Paterson.

## SY26-27 NJ rollover status

`reporting__terms` (K-2 `LIT`+`PLIT`, 3-4/5-8 `LIT`-only) is built and verified
for Newark, Paterson, and Camden, and serves both data models unchanged.

**Both Expected Assessments models need their own row set.** Regenerated and
counted at the current commit:

| Row set                       | Aimline (by-levels range) | Internal K-8 (V1 range) |
| ----------------------------- | ------------------------- | ----------------------- |
| NJ (Newark, Paterson, Camden) | 758                       | 614                     |
| Miami                         | 412                       | 269                     |

**The by-levels range takes the `--no-scaffold` set, not the default combo
set.** An earlier version of this table listed the combo output (878 NJ + 416
Miami = 1,294), written when K-2 was expected to stay on the internal method
inside the 18-column range. That is not what shipped: aimline runs K-8 and
supplies its own goals, so no grade needs the trajectory scaffold. What is in
the sheet, verified against the staging model, is the `--no-scaffold` set --
Newark 282, Paterson 282, Camden 194, Miami 412 = 1,170 AY2026 rows, all four
regions pasted.

The aimline set is larger at every grade despite scaffolding none of them,
because it splits each row into `Below` / `Well Below` (523 `Both` rows become
1,046) while the 16-column V1 range has no cohort. Verified in the generated
output: internal 3-8 carries 112 rows at `pm_goal_include = false` (the scaffold
extends to every grade) where combo 3-8 carries zero (aimline supplies the
goal).

**Both row sets are pasted, all four regions -- verified against the staging
models, not assumed.** Query the staging model rather than trusting a note here;
the sheets are live and a note goes stale the moment T&L edits a tab.

| Range              | Newark | Paterson | Camden | Miami | Total |
| ------------------ | ------ | -------- | ------ | ----- | ----- |
| V1 16-col, PM rows | 244    | 244      | 126    | 269   | 883   |
| By-levels 18-col   | 282    | 282      | 194    | 412   | 1,170 |

The V1 range also carries 144 Benchmark rows per region for AY2026; the
by-levels range carries none, by design.

```sql
select academic_year, region, count(*)
from <dataset>.stg_google_sheets__dibels__expected_assessments_by_levels
group by 1, 2
```

**Miami: the boundary rule is now verified** (see _`PLIT` boundary rule_ above
-- same rule, with two unresolved divergences), so that is no longer the
blocker.

**Operating policy for Miami, decided deliberately: derive from the calendar and
ship it.** Do not hold the rollover waiting on T&L to explain a divergence.
Apply the clean rule, generate the rows, and accept that a window cut around
state testing may need correcting later -- a correctable row beats a missing
one, and Miami's PM windows are not reconstructable from any other source we
hold. Flag derived rows as derived so a later correction is cheap; do not
re-litigate the `PLIT3` question above before generating.

**Miami SY26-27 is generated.** 44 `reporting__terms` rows
(`generate_miami_lit_plit_rows.py`) and 416 `Expected Assessments` rows
(`generate_pm_expected_assessments_rows.py --regions Miami`). What the
generators encode, all from the T&L SY27 doc's Miami tab:

- **11 rounds, season split 5 + 6.** The MOY Benchmark window (`1/5 - 1/22`)
  falls between rounds 5 and 6. AY2025 Miami ran 6 rounds (3+3), so the shape
  changed -- do not pattern-match off last year.
- **Grade bands stay on AY2025's scheme** (`0,1,2` with `LIT`+`PLIT`, `3,4` and
  `5,6,7,8` `LIT`-only), NOT the doc's own K / 1-3 / 4-5 / 6-8 groupings, whose
  `1-3` band would straddle the K-2 / 3-8 boundary and strip `PLIT` from grades
  1-2. Every Miami round shares identical dates across bands, so the band split
  only matters for `PLIT`. The doc's groupings still drive measures.
- **Cohorts alternate by round** -- odd rounds test `Below` + `Well Below`, even
  rounds `Well Below` only. **This applies to K-2 as well as 3-8**, which NJ's
  generator did not anticipate: its K-2 branch hardcoded `Both`, correct for NJ
  and wrong for Miami. Now reads the round's own cohort via `k2_cohort()`; NJ
  output re-verified byte-identical (878 rows) after the change.
- **Measure progression**: round 1 gives grade 1 `NWF` alone (the doc splits
  "G1" from "G2-3"); rounds 2-5 give grades 1-3 `NWF` + `ORF`; from round 6
  `NWF` drops from grades 1-3 and `Maze` is added to grades 4-8. That round-1
  split is the ONLY scaffold-fill in Miami's whole set -- grade 1 / `ORF` /
  `LIT1` gets `pm_goal_include = false` (4 rows).
- **`PM_Goal_Criteria` is `AND` for Miami too.** An earlier draft of this
  section said to leave it blank because Miami's AY2025 rows are blank -- that
  was wrong. The instruction is explicit and network-wide: T&L requires students
  to meet ALL tested standards per round this year. Miami's blank AY2025 values
  are a gap, not a precedent to preserve.
- **`PLIT1.start` is derived**, not copied from the Benchmark start -- Miami's
  `BOY` window opens a month into the year (`2026-09-08`), so NJ's shortcut
  would put `PLIT1` a month late. Uses the first in-session day of AY2026
  (`2026-08-12`), which is what AY2025 approximates.

Still open for Miami: **cohort mechanics from Miami's 3-8 leads** (#3834). The
doc's alternation is encoded as written, but nobody has confirmed the intent
behind alternating rather than testing both cohorts every round.
