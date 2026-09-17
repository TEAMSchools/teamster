# STAT Dashboard Data Model

Reference for the **State Testing Analysis Tool (STAT)** — the Tableau workbook
KTAF uses to read state assessment results across Newark, Camden, Miami and
Paterson.

Row counts and other measurements in this document were taken against production
on 2026-09-16. They are here to make a claim checkable, not because they stay
true; re-run the query beside a number before relying on it.

## What is STAT?

One workbook, two reporting models, and a Google Sheet of hand-entered
comparison figures. It answers two different questions that people routinely
confuse:

- **How did our students do?** Student-level scores, proficiency bands, growth
  year over year, and teacher rosters.
- **How did we do against everyone else?** KTAF proficiency next to the host
  city, the state, and (in Miami) a named set of neighborhood schools.

The second question has no warehouse source. Nobody publishes comparison
proficiency in a form we can ingest, so it is typed into a sheet by hand. Most
of the surprises in this pipeline come from that fact.

## The workbook

Exposure `state_testing_analysis_tool` in
`src/dbt/kipptaf/models/exposures/tableau.yml`. Tableau LSID
`31b6a4a9-e0ca-479b-8f44-0daaa52e109b`, project `Production`.

Six published views and one hidden dashboard, drawing on two embedded extracts:

| View                      | Datasource                                       |
| ------------------------- | ------------------------------------------------ |
| Landing Page              | `rpt_tableau__state_assessments_dashboard`       |
| Overview                  | `rpt_tableau__state_assessments_dashboard`       |
| Demographics              | `rpt_tableau__state_assessments_dashboard`       |
| Teacher/Student Roster    | `rpt_tableau__state_assessments_dashboard`       |
| Proficiency YoY           | `rpt_tableau__state_assessments_dashboard`       |
| **Advanced Comps**        | `rpt_tableau__state_assessments_dashboard_comps` |
| _Sarba's Report_ (hidden) | `rpt_tableau__state_assessments_dashboard`       |

**Only Advanced Comps reads the comps model.** Three worksheets sit on it —
`Advanced Comps - 3-Column`, `- 5-column` and `- Header` — plus an orphan
worksheet `Sheet 52` that is bound to the comps datasource but placed on no
dashboard. A change confined to `rpt_tableau__state_assessments_dashboard_comps`
cannot move any number on the other five views.

Both datasources are **embedded extracts**. The Tableau MCP cannot read
calculated-field text and returns HTTP 500 on `get-datasource-metadata` for an
embedded extract, so any question about what the workbook does with a field is
answered by downloading the `.twb` — see the `tableau-workbook-xml` skill.

## Scores: the NJ dual-vendor union

The NJ DOE has **changed vendors for all state testing**, from **Pearson Access
Next** to **Cambium TIDE**. The cutover is a date, not a per-assessment rollout:

| administration                       | vendor  |
| ------------------------------------ | ------- |
| through **December 2025**            | Pearson |
| **Spring 2026** and everything after | Cambium |

December 2025 was the last Pearson data KTAF implemented. Every NJ
administration from Spring 2026 onward is Cambium.

Two consequences worth stating plainly. The Pearson relations in the union are
**history**, not a live feed -- they will not accrue new rows, so a gap in one
of them is a gap in the past and cannot be fixed by a re-pull. And
`stg_pearson__njgpa` is **moot**: the Pearson form of that test is retired.

[`src/dbt/cambium/CLAUDE.md`](https://github.com/TEAMSchools/teamster/blob/main/src/dbt/cambium/CLAUDE.md)
describes NJSLA and NJSLA Science as Pearson-only, and that remains **correct**
as a statement about the pipeline: the vendor has changed, but Cambium score
files for those two assessments have not arrived yet, so nothing ingests them.
Update it when the first files land, not before.

The union happens at kipptaf `int_pearson__all_assessments`, over five
relations:

```text
kippnewark_pearson.int_pearson__all_assessments    ]
kippcamden_pearson.int_pearson__all_assessments    ]  Pearson
kipppaterson_pearson.int_pearson__all_assessments  ]

kippnewark_cambium.stg_cambium__njgpa              ]  Cambium
kippcamden_cambium.stg_cambium__njgpa              ]
```

**The model's name is a misnomer and a rename is pending.** It carries two
vendors. Anything reading it should not assume Pearson.

Cambium ships a completely different schema — snake_case headers against
Pearson's camel case, with only 11 of 225 column names in common — so
`stg_cambium__njgpa` in the cambium package does the vocabulary mapping into the
Pearson-shaped columns before kipptaf ever sees it. The two vendors' aligned
columns are computed in two different places and have to be kept in step by
hand:

| Vendor  | Where the aligned columns are computed                    |
| ------- | --------------------------------------------------------- |
| Pearson | `int_pearson__all_assessments` in the **pearson** package |
| Cambium | `stg_cambium__njgpa` in the **cambium** package           |

A cambium-package model cannot call into the pearson package, so the race, IEP
and ML mappings are deliberately restated rather than shared. If you change one,
change the other.

`assessment_version` is what tells the two apart downstream: `NJGPA` is the
retired Pearson form, `NJGPA-A` the Cambium adaptive form. They use different
score scales and therefore different graduation cut scores, which is why the
cut-score sheet joins on `assessment_version` and not on `assessment_name`.

Production distribution:

| `assessment_version` | kippnewark | kippcamden | kipppaterson |
| -------------------- | ---------: | ---------: | -----------: |
| PARCC                |     12,637 |      2,988 |            — |
| NJSLA                |     32,278 |     11,931 |          324 |
| NJSLA Science        |      4,985 |      1,819 |          116 |
| NJGPA (Pearson)      |      3,081 |      1,049 |            — |
| NJGPA-A (Cambium)    |        564 |        249 |            — |

Paterson does not sit for NJGPA and has `stg_pearson__njgpa` disabled; it does
not import the cambium package at all.

Florida is a separate leg entirely — `int_fldoe__all_assessments`, unioned in at
the reporting view rather than here.

### The dashboard publishes a rolling window, not all history

`rpt_tableau__state_assessments_dashboard` filters scores to
`academic_year >= current_academic_year - 7`, so roughly the last seven years
reach the workbook while the models underneath retain everything back to PARCC.

This is worth checking before spending effort on an old defect. A flagged score
or an unrepaired identifier in a year that has rolled out of the window is not
visible to anyone and does not need fixing — the 8 unmatchable rows below are
all academic year 2017 or 2018 and fall into exactly that category. Confirm the
filter rather than trusting this sentence; the constant is in the model.

## Repairing a student number that does not resolve

Assessment rows arrive keyed on the vendor's `localstudentidentifier`, which is
supposed to be the network `student_number`. Sometimes it isn't, and the
assessment row then fails to join to an enrollment and disappears from the
dashboard silently.

The repair chain, in kipptaf `int_pearson__all_assessments`:

```sql
coalesce(x.student_number, s.localstudentidentifier) as localstudentidentifier
-- x = stg_google_sheets__pearson__student_crosswalk, on student_test_uuid
```

**The repair is applied after the union, so it already covers every vendor.**
There is no Pearson-specific and Cambium-specific version of this: one sheet,
one join, keyed on the test UUID. A Cambium correction goes in the same sheet as
a Pearson one and works with no code change, because `stg_cambium__njgpa`
already aliases `student_test_uuid` to `studenttestuuid` before the union.

The sheet is named for Pearson only because Pearson was the sole vendor when it
was built. Renaming it is deferred, not forgotten -- see _Deferred work_ below.

`test_incorrect_student_number_pearson` is the detector. It returns any row from
2017 onward whose `localstudentidentifier` is null or fails to resolve to an
enrollment, and its failure rows carry the `studenttestuuid` you paste into the
sheet. It reads the unioned model, so it covers Cambium as well. Its own name is
still Pearson-flavoured; renaming it, and renaming
`int_pearson__all_assessments`, remain open.

**The detector is non-blocking.** It sets no `severity`, so it inherits
kipptaf's project default of `warn`. A failing row does not fail a build or CI —
it produces a warning nobody is required to read, which is why the 9 Cambium
rows below have sat unresolved since the Spring 2026 administration. Raising it
to `error` is a decision about whether an unrepaired score should stop a deploy,
not an oversight to quietly correct.

Its failure rows contain `firstname` and `lastorsurname`. **Those are student
PII — never paste them into a PR, an issue, or Slack.** Quote the UUID and the
count.

### Failure modes -- and they are modes, not vendors

The distinction that matters is how the identifier is broken, not who sent it.

- **Absent.** The identifier arrives null, so the join has nothing to match on.
  Mechanically recoverable: `statestudentidentifier` resolves to the same
  student. No human judgement required.
- **Present but wrong.** No rule recovers the intended student, so a person has
  to decide who the test belongs to. The crosswalk sheet is the only mechanism
  for this, and it is permanent.

The second mode is the dangerous one. A wrong identifier that happens to be a
_valid_ `student_number` resolves to the wrong student silently, and the
detector never fires because the join succeeds. That is not hypothetical: the
Paterson rows in the spec below FK'd into Newark students and passed every test
until someone went looking.

**Do not read these modes as vendor properties.** As of the Spring 2026
administration all 11 outstanding Pearson failures are the wrong mode and all 9
Cambium failures are the absent mode, so the two currently look like vendor
traits. They are not. That Cambium reading comes from a single file -- 850 rows,
one administration -- against eight years and ~71,000 rows of Pearson history.
Cambium's `local_student_identifier` in that file is clean where populated (zero
non-numeric values, 804 of 804 non-null values resolving 1:1, only 5- and
6-digit widths), but one file is no basis for assuming the next one will be.
Triage by mode; never conclude a vendor cannot produce a mode.

### The third category: no enrollment in the year the test was taken

Some failing rows are neither mode, and **the crosswalk cannot repair them.**
Check for this before entering anything in the sheet.

The repair only overrides `localstudentidentifier`. The join still needs
`student_number`, `academic_year` and `_dbt_source_project` to land together on
an enrollment with `rn_year = 1`. When the student has no enrollment in that
year and district, no value in the sheet makes the join succeed -- the row stays
flagged and the sheet gains an entry that does nothing and never expires.

As of 2026-09-17 this is 8 of what were 20 outstanding rows -- the other 12 have
been repaired -- and they are 4 NJSLA and 4 PARCC, 6 Newark and 2 Camden,
**every one of them academic year 2017 or 2018**. All 8 match exactly one
student by name somewhere in PowerSchool -- a different year, a different
district, or both -- and none of them match in the year the test belongs to.
Four also match a single student by state id on that widened search.

That a name resolves on the widened search is what makes this category
deceptive: it looks solvable right up to the point where you notice the year
does not line up. The remaining explanations are an Ops or enrollment-history
question, not an identifier question:

- the student genuinely was not at that region that year, so the test row is
  filed to the wrong district;
- the enrollment record for 2017 or 2018 is missing, a gap in the PARCC-era
  history rather than a broken id;
- the name match is a different person who shares the name.

The concentration in the two oldest years points at the second. Compare with the
8 Paterson orphans in
[#3956](https://github.com/TEAMSchools/teamster/issues/3956), which are the same
shape: rows no model-side join can resolve, tracked as an Ops item rather than
repaired in dbt.

### Open recommendation — resolve Cambium nulls from the state id

Not implemented. Recorded here because the evidence is already gathered.

Every one of the 9 Cambium rows currently failing the test (6 Camden, 3 Newark)
carries a populated `statestudentidentifier`, and **all 9 resolve 1:1 to a
PowerSchool enrollment** for the same academic year and district — zero null
state ids, zero fan-out. So the Cambium failure mode is mechanically recoverable
and does not need a human at all:

```sql
coalesce(
    x.student_number,          -- crosswalk sheet, for a wrong value
    s.localstudentidentifier,  -- what the vendor sent
    sid.student_number         -- proposed: resolved from statestudentidentifier
) as localstudentidentifier
```

The precedent exists in the building: the preliminary-scores branch of
`rpt_tableau__state_assessments_dashboard` already joins `e.state_studentnumber`
this way. Cost is a new dependency on `base_powerschool__student_enrollments`
inside the intermediate, region-keyed and `rn_year = 1`; there is no cycle,
because enrollments does not read the assessment side.

**It addresses one mode and does not replace the sheet.** The fallback would
clear the absent mode permanently. The present-but-wrong mode has no automated
recovery at all, so the crosswalk stays regardless -- for every vendor, however
clean a given file looks. Read this as reducing volume, not as removing the
hand-entry step.

## Comparisons: two independent paths

The single most common mistake in this pipeline is assuming there is one comps
calculation. There are two, they read different things, and they disagree by
design.

```text
                    stg_google_sheets__state_test_comparison_demographics
                    (hand-entered City / State / Neighborhood figures)
                              |                          |
                              |                          |
         +--------------------+                          +------------------+
         |                                                                  |
         v                                                                  v
  rpt_tableau__state_assessments_dashboard                 rpt_tableau__state_assessments_dashboard_comps
  `state_comps` CTE                                        `appended` CTE, third branch
         |                                                                  ^
         | filters to Total / All Students                                  |
         | pivots to 3 wide columns                                         | unions with
         v                                                                  |
  proficiency_city / _state /                              int_tableau__state_assessments_demographic_comps
  _neighborhood_schools                                    (KTAF's OWN results, aggregated from student rows)
         |                                                                  |
         v                                                                  v
  five views                                                        Advanced Comps
```

**Path one — embedded in the score view.** The `state_comps` CTE inside
`rpt_tableau__state_assessments_dashboard` reads the sheet directly, filters to
`comparison_demographic_group = 'Total'` and
`comparison_demographic_subgroup = 'All Students'`, and pivots the three
comparison entities into three wide columns (`proficiency_city`,
`proficiency_state`, `proficiency_neighborhood_schools`). No demographic
breakdown, no KTAF-derived rows. This is what most views show.

**Path two — the long comps model.**
`rpt_tableau__state_assessments_dashboard_comps` unions the sheet rows with
KTAF's own results computed from student-level scores in
`int_tableau__state_assessments_demographic_comps`, keeps every demographic
subgroup, and emits one row per comparison. Only Advanced Comps reads it.

A number that differs between Overview and Advanced Comps is usually these two
paths, not a bug.

The sheet is also a **metadata** source, separately from being a comps source:
`int_tableau__state_assessments_demographic_comps` reads it in its
`test_code_metadata` CTE purely to look up `school_level`, `grade_range_band`
and `discipline` per test code. A test code absent from the sheet loses that
metadata for KTAF's own rows.

### Interim comps from media, before the official files

Official comparison files do not arrive in usable form until roughly November.
In the meantime the state's headline results circulate through press coverage
and district decks, and those figures are entered as interim comps so the
dashboard is not blank for the current year. The rule of thumb is that **we do
not make rules of comparison, we report what the state reports** -- an interim
figure is loaded as published, not adjusted or withheld because a year-over-year
comparison would be awkward.

Three things are always true of a media-sourced figure, and they constrain what
it can do.

**There is no denominator.** Press figures give a percentage and nothing else,
so `total_students` is left empty. That used to destroy the figure on its way to
Advanced Comps; the model now falls back to the reported percentage, so an
interim comp populates all six views. The counts stay empty, which is the honest
representation of what a press figure contains. See _Every comps group is one
source row_ below.

**Only `Total` / `All Students`.** Media reporting carries no demographic
breakouts, so an interim load fills exactly one demographic row per test code
and region. Every subgroup row waits for the official file.

**ALG01 arrives mixed.** Media figures never separate Algebra I taken in middle
school from Algebra I taken in high school; one combined number is published.
The interim convention is to write that same figure to **both** the MS and the
HS `school_level` rows, with `remove_row = FALSE` on both. This is deliberately
imprecise and known to be so -- the weighted MS/HS rollup that `remove_row`
exists to build needs counts, which an interim load does not have. It is
corrected when the official file lands.

### Every comps group is one source row, and the percentage falls back

`grouped_comps` in `rpt_tableau__state_assessments_dashboard_comps` re-derives
`percent_proficient` as `safe_divide(sum(proficient), sum(total))` rather than
carrying the source value through. The intent is weighting: a group assembled
from several rows should be sized, not averaged.

**Measured 2026-09-17: it never assembles more than one row.** All 13,897 groups
have `source_rows = 1`, and none mixes a row that has a denominator with one
that does not. The re-derivation aggregates a single row every time.

That is harmless where a denominator exists and destructive where one does not
-- `safe_divide` returns null, so a percentage the sheet actually carried
arrived blank. Every denominator-less row behaved that way, which is what made
interim media comps unusable in Advanced Comps while working fine in the other
five views, since the `state_comps` CTE reads `avg(percent_proficient)` directly
and never recomputes.

The model now falls back:

```sql
if(
    weighted_percent_proficient is null and source_rows = 1,
    reported_percent_proficient,
    weighted_percent_proficient
) as percent_proficient
```

The `source_rows = 1` guard is the part that matters. One-row groups are a
property of today's grain, not a guarantee -- so if the grain ever changes and a
group gains rows, this degrades to null rather than silently averaging two
percentages unweighted, which would be wrong in a way nobody would notice.

Measured against production before shipping: 13,897 rows before and after, 12
rows move from null to a value, **zero** existing values change,
`total_students` unchanged, and 2 `region_outperformed` booleans flip because a
recovered percentage can now participate in the Region self-join.

**A flag on the sheet was considered and rejected for this job.** A
`preliminary` boolean would be a second, hand-maintained source of truth for
something the data already states -- `total_students is null` identifies exactly
these rows -- and the two can disagree, with no test to catch it. Provenance is
a fair reason to add such a column later; driving the arithmetic is not.

The counts remain null on these rows: Advanced Comps shows the percentage with
blank `total_students` and `total_proficient_students`, which is the honest
representation of what a press figure contains.

### Reading the sheets: ADC, not the BigQuery MCP

Both Google Sheets sources behind this dashboard are Drive-backed externals. The
BigQuery MCP service account has no Drive scope and returns 403 on them. **ADC
does have Drive scope**, so a Python client reads the external directly and sees
the sheet live — which is the only way to answer "did that paste land" without
waiting on a build.

Do not reach for a `--target staging` build to inspect rows. It is a shared
write that needs authorization, and the table it produces is frozen at build
time, so it answers a different question than the one usually being asked. Build
only when something downstream has to read the result.

The same applies to the prod `stg_*` table: it is a table, not a live read, so
it reports pre-edit values indefinitely. Judging current sheet contents from it
is a standing trap.

### A missing value means the state did not provide it

That is the whole rule. `total_students` empty does not mark a row as
provisional, second-rate or media-sourced — it means the state published a
percentage and no count for that cell. It happens in press figures, which almost
never carry counts, and it happens in official files, which sometimes omit them
for a particular subgroup. Same cause, one rule.

So do not infer provenance from a null. The AY2024 rows missing a denominator
for one subgroup in two regions are official data with a gap, not a press
figure, and nothing in the row distinguishes them.

**To see which rows are affected, ask the sheet rather than trusting a list:**

```sql
select academic_year, region, comparison_entity,
       count(*) as rows_affected,
       count(distinct aligned_test_code) as test_codes,
       string_agg(distinct comparison_demographic_subgroup) as subgroups
from `teamster-332318`.kipptaf_google_sheets.src_google_sheets__state_test_comparison_demographics
where total_students is null and percent_proficient is not null
group by 1, 2, 3
order by 1 desc, 2, 3
```

Read it through ADC, not the BigQuery MCP — see above. This is derived, so it is
never out of date, which a written inventory of loads cannot promise.

### Comparison entities

| `comparison_entity`    | Origin  | Meaning                                |
| ---------------------- | ------- | -------------------------------------- |
| `City`                 | sheet   | the host city LEA                      |
| `State`                | sheet   | statewide                              |
| `Neighborhood Schools` | sheet   | a named comparison set, **Miami only** |
| `Region`               | derived | KTAF in that region                    |
| `KTAF NJ`              | derived | all NJ regions combined                |
| `KTAF FL`              | derived | Miami                                  |

`region_matched`, `region_outperformed` and `region_matched_or_outperformed` are
computed by self-joining each row to its `comparison_entity = 'Region'` partner
on ten columns, including `comparison_demographic_subgroup`. **A row whose
subgroup string has no Region partner gets `false`, not null** — the join yields
null and `if(null, true, false)` collapses it. A missing comparison and a lost
comparison are indistinguishable on the dashboard.

### Controlled vocabulary

`comparison_demographic_subgroup`, after the normalization in
`stg_google_sheets__state_test_comparison_demographics`:

`African American` · `All Students` · `American Indian` · `Asian` ·
`Economically Disadvantaged` · `Female` · `Hispanic` · `Male` · `ML` ·
`Native Hawaiian` · `Non Economically Disadvantaged` · `Other` ·
`SE Accommodation` · `Students With Disabilities` · `White`

Guarded by an `accepted_values` test at `severity: error`. Extend it
deliberately when a genuinely new subgroup appears — never to make a build pass.

Test codes carried by the sheet: `ELA03`–`ELA10`, `ELAGP`, `MAT03`–`MAT08`,
`MATGP`, `ALG01`, `ALG02`, `GEO01`, `SCI05`, `SCI08`, `SCI11`, `SOC08`.

`ALG01` is the awkward one. Overall comparisons split MS from HS, but official
sources publish demographic breakdowns only for grades 8+ combined. The sheet
therefore carries HS-only ALG01 rows flagged `remove_row = true`, which the
staging model filters out of the main branch and re-aggregates in a second
branch into a single weighted `Total` / `All Students` row. `ALG02` totals are
10th grade only and `GEO01` follows the same pattern for grades 9 and 10, while
their demographic rows include every student who took the test.

## Known issues

### Resolved — the subgroup vocabulary was split, and comparisons read false

Fixed in this model. Recorded because the shape recurs.

The sheet used two spellings that the KTAF-derived rows never use, and the
self-join above matches on that exact string:

| Sheet side                  | Derived side                     |
| --------------------------- | -------------------------------- |
| `Black Or African American` | `African American`               |
| `Non-Econ. Disadvantaged`   | `Non Economically Disadvantaged` |

The effect was total and silent: **0 of 337** `Black Or African American` rows
and **0 of 671** `Non-Econ. Disadvantaged` rows ever read
`region_outperformed = true`, while spelling-matched `Hispanic` read true on 145
of 296. Normalizing flips 239 rows to true and none to false.

The two labels broke differently, and one has a date:

- `African American` was used by the NJ regions for **AY2018–2023**.
- `Black Or African American` appears in NJ for **AY2024 only**, and in Miami
  for AY2020–2024.
- `Non-Econ. Disadvantaged` is used everywhere, every year.

So the NJ Black/African American comparison **worked through AY2023 and broke
when AY2024 was entered**, which would have read as "the 2024 comps look worse."
Miami's never worked. The economic-disadvantage comparison has never worked
anywhere, in any year.

Normalizing changes no aggregate — 13,897 rows before, 13,897 distinct grouping
keys after, so nothing merges and `percent_proficient`, `total_students` and
`total_proficient_students` are byte-identical. It also fixes a sort: the
workbook carries a `<manual-sort>` dictionary on this field listing the derived
vocabulary, so the two sheet spellings previously fell to the end of the axis.

#### Exactly what moved

Measured against production on 2026-09-16 by simulating the normalization on the
live view, before the fix shipped. Kept here so the change stays auditable after
the pull request is closed.

Only the three comparison booleans move. `Black Or African American` gains 85 of
337 rows; `Non-Econ. Disadvantaged` gains 154 of 671. One row additionally gains
`region_matched`. Nothing flips the other way.

`Black Or African American`, 85 flips:

| academic year | region   | rows | flips |
| ------------- | -------- | ---: | ----: |
| 2020          | Miami    |   45 |     0 |
| 2021          | Miami    |   45 |     4 |
| 2022          | Miami    |   45 |     7 |
| 2023          | Miami    |   45 |     8 |
| 2024          | Camden   |   38 |    19 |
| 2024          | Miami    |   45 |    13 |
| 2024          | Newark   |   38 |    31 |
| 2024          | Paterson |   36 |     3 |

`Non-Econ. Disadvantaged`, 154 flips:

| academic year | region   | rows | flips |
| ------------- | -------- | ---: | ----: |
| 2018          | Camden   |   38 |    12 |
| 2018          | Newark   |   38 |    18 |
| 2020          | Miami    |   45 |     0 |
| 2021          | Camden   |   33 |    14 |
| 2021          | Miami    |   45 |     0 |
| 2021          | Newark   |   38 |    17 |
| 2022          | Camden   |   35 |    11 |
| 2022          | Miami    |   45 |     2 |
| 2022          | Newark   |   38 |    17 |
| 2023          | Camden   |   36 |    14 |
| 2023          | Miami    |   45 |     3 |
| 2023          | Newark   |   38 |    19 |
| 2023          | Paterson |   38 |     0 |
| 2024          | Camden   |   38 |    10 |
| 2024          | Miami    |   45 |     0 |
| 2024          | Newark   |   38 |    16 |
| 2024          | Paterson |   38 |     1 |

Newark 2024 is the largest single cell, 31 of 38 rows. The pre-2024
`Black Or African American` rows are all Miami, because the NJ regions only
switched to that spelling at 2024.

**A zero-flip cell is not a failed match.** Miami 2020 and 2021 do find their
Region partner; KTAF Miami simply did not outperform in those cells. Flip count
and match count are different things.

To re-check after a rebuild, group
`rpt_tableau__state_assessments_dashboard_comps` by year, region and subgroup
for the sheet-sourced entities (`City`, `State`, `Neighborhood Schools`) and
count `region_outperformed`. The old spellings should return no rows at all. A
subgroup still reading zero across every test code is the signature of a
vocabulary mismatch, not of poor performance.

### Open — 195 comparison rows still find no Region partner

Normalizing the two labels does not close the gap entirely. 65
`Black Or African American` rows and 130 `Non-Econ. Disadvantaged` rows still
match no Region row, and the problem is broader than those two subgroups: **573
of 870 `Neighborhood Schools` rows have no Region partner at all.**

Not diagnosed. The self-join keys on ten columns and the likely culprits are
`school_level` and `grade_range_band`, which reach the sheet rows as typed
values but reach the derived rows through `any_value()` in the
`test_code_metadata` lookup. Start there, not at the subgroup labels.

### Open — comparison data stops at academic year 2024

The sheet carries nothing for AY2025 or later, for any region. Official
comparison files do not arrive until roughly November, so the intervening months
are covered by transcribing figures out of whatever NJDOE and district
presentations circulate. See the `stat-dash` skill for that procedure.

Coverage is also uneven historically — NJ has no 2019 or 2020 rows (COVID), and
Paterson begins at 2023.

### Deferred work on the crosswalk

All of this was considered and deliberately postponed in September 2026. The
sheet is used as-is meanwhile, with Cambium corrections going into the existing
tab alongside the Pearson ones.

1. **Rename it off the Pearson name.** It serves every NJ vendor. A rename
   touches the spreadsheet, the named range, the source entry, `sheet_range`,
   the staging model and its properties, the Dagster asset key, and the one
   `ref()` in `int_pearson__all_assessments` -- and leaves two orphaned
   relations in `kipptaf_google_sheets` that dbt will not drop. The August 2026
   Cambium ingestion spec logged this first.
2. **Add a vendor column.** Provenance only; no UUID appears under both vendors
   (72,021 rows, 72,021 distinct UUIDs), so it would never be part of the join
   key.
3. **Move the per-localid corrections into district intermediates and retire the
   sheet.** This is the endpoint the Paterson ID-translation spec names: _"File
   a follow-up issue to move the per-localid corrections to kippnewark /
   kippcamden intermediates analogous to the Paterson pattern; then the
   crosswalk can be retired."_ No such issue was found open as of 2026-09-16.
   Note that this only works for corrections with a derivable rule -- the
   present-but-wrong mode has none, so some manual surface survives any version
   of this.
4. **Close two staging-layer gaps.** The model has no uniqueness test and no
   column descriptions, which the staging-layer rule requires.

The relevant precedent for (3) is that this repo fixes _systematic_ identifier
problems structurally and _one-off_ ones with a sheet row. Paterson's 440 rows
all carried district SIS IDs, and the fix was a join against
`stg_powerschool__studentcorefields.prevstudentid` at the kipppaterson layer,
not 440 sheet entries. The 69 rows in this sheet are the one-off kind: raw
values span 4 to 9 digits correcting to 5 or 6, which is scattered data entry
error, not one translatable id space.

### Open — the crosswalk sheet holds 13 rows that do not hold up

Audited 2026-09-17: all 81 crosswalk rows were replayed through the matching
rules in
[`analyses/state_assessment_tiered_crosswalk_match.sql`](https://github.com/TEAMSchools/teamster/blob/main/src/dbt/kipptaf/analyses/state_assessment_tiered_crosswalk_match.sql)
using each row's raw pre-repair identifier, and the rules' pick was compared
against what a human had entered.

| outcome                |  rows | meaning                                                  |
| ---------------------- | ----: | -------------------------------------------------------- |
| agrees                 |    66 | the rules independently reach the same student           |
| ambiguous              |     2 | tiers fire on more than one student; needs a person      |
| `no_pick_identity`     |     7 | enrolled that year, but no tier is satisfied             |
| `no_pick_not_enrolled` |     6 | the entered student has no enrollment in the test's year |
| **disagrees**          | **0** | —                                                        |

**Zero disagreements across 81 hand-entered rows** is the headline: the rules
never contradict a human judgement, which is what makes them safe to run as a
proposer rather than an authority.

The 13 that do not reproduce are the thing to fix, and they are two different
problems:

- **The 6 `no_pick_not_enrolled` rows are inert.** They are the unmatchable
  category described above, already sitting in the sheet. The crosswalk
  overrides the identifier, but the downstream join still fails on academic year
  and district, so these entries do nothing at all. They are candidates for
  removal, not repair -- but confirm against the enrollment history first, since
  an enrollment record added later would make them live.
- **The 7 `no_pick_identity` rows are unexplained.** The student is enrolled in
  the right year and district, but name, date of birth and state id do not
  satisfy any tier. Either the person entering had context the fields do not
  carry, or a name changed between the vendor file and PowerSchool. These need a
  human to look, not a rule change -- resist adding a tier to absorb them until
  a deterministic, generalizable pattern is actually visible, which is the same
  discipline the AP protocol applies to its own no-match bucket.

The 2 ambiguous rows are working as designed: more than one student satisfies
the tiers, so the rules decline rather than guess.

Re-run the audit after any batch of sheet entries. The procedure is in the
`stat-dash` skill; it writes per-row detail to a local file and reports only
counts, because the per-row output carries student identifiers.

### Open — the exposure has no `url`

`state_testing_analysis_tool` omits `url:`, which
[`src/dbt/kipptaf/CLAUDE.md`](https://github.com/TEAMSchools/teamster/blob/main/src/dbt/kipptaf/CLAUDE.md)
lists as required for every exposure. Cosmetic, but it is the reason the
workbook link has to be looked up by LSID.
