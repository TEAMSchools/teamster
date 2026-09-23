---
name: stat-dash
description: >-
  Use when any question or task touches the State Testing Analysis Tool (STAT)
  dashboard or its lineage. Triggers: the "stat dash" or state assessment
  dashboard, entering or bootstrapping state/city/neighborhood comparison
  figures into the comps sheet, a comparison reading false or a comp not
  appearing, a student's state assessment score missing from the dashboard, the
  Pearson-to-Cambium NJ vendor migration, the student crosswalk sheet, or
  working on rpt_tableau__state_assessments_dashboard,
  rpt_tableau__state_assessments_dashboard_comps,
  int_tableau__state_assessments_demographic_comps,
  stg_google_sheets__state_test_comparison_demographics,
  stg_google_sheets__pearson__student_crosswalk, int_pearson__all_assessments or
  stg_cambium__njgpa and their upstream models.
---

# STAT Dashboard

## Always read first

- Reference doc:
  [`docs/models/stat-dashboard-data-model.md`](../../../docs/models/stat-dashboard-data-model.md)

It is authoritative for lineage, the dual-vendor union, the two comps paths, the
controlled vocabulary, and the open issues. Read it before answering anything,
not just before editing.

**Three facts that cause most of the wrong answers here:**

- `academic_year` is the STARTING year of the school year. Testing happens in
  the spring, so a source reporting "2026 results" means the 2025-2026 school
  year, which is `academic_year = 2025`. The published label always runs one
  ahead of the warehouse value. Confirm before generating any row.
- **There are two comps calculations, not one.** The `state_comps` CTE inside
  `rpt_tableau__state_assessments_dashboard` and the separate
  `rpt_tableau__state_assessments_dashboard_comps` read different things. A
  number that differs between Overview and Advanced Comps is usually that, not a
  bug. See the reference doc.
- `int_pearson__all_assessments` carries **both** Pearson and Cambium. Its name
  is a known misnomer. Never assume a row in it is Pearson.
- **The vendor changed on a date, not per assessment.** Through December 2025 it
  is Pearson; Spring 2026 and everything after is Cambium, for all NJ state
  testing. So the Pearson relations are history and will not gain rows -- a gap
  in one cannot be fixed by a re-pull -- and `stg_pearson__njgpa` is moot.

---

## START HERE: making a change to this pipeline

Run these in order before editing any SQL.

1. **Clarify the change with the requester.** Invoke `superpowers:brainstorming`
   (`Skill` tool) and pin down, one question at a time: what changes, at which
   grain, for which region and academic year, and what the expected effect on
   the dashboard is — more rows, different booleans, changed labels, or none
   because it is a refactor.
2. **Read the reference doc**, as required above.
3. **Map the impact.** `mcp__dbt__get_model_parents` /
   `mcp__dbt__get_model_children` on each target, cross-checked against the
   exposure's `depends_on`.
4. **State the model-specific risks before implementing:**
   - **Which of the two comps paths does this touch?** Changing the sheet
     touches both. Changing `rpt_tableau__state_assessments_dashboard_comps`
     touches only Advanced Comps.
   - **Does it move a string the ten-column self-join keys on?** If so, rows
     silently lose their Region partner and read `false`, not null.
   - **PII.** Student-level rows live in
     `rpt_tableau__state_assessments_dashboard` and in the failure rows of
     `test_incorrect_student_number_pearson`, which carry student names. Never
     paste them outbound.
   - Contract enforcement on both `rpt_` models and both staging models.
5. **Implement**, then **validate** — build the affected models one at a time
   and run the audit query from the relevant procedure below.

---

## Procedure: List refs, lineage, or sources

Do not search the codebase. Read the exposure `state_testing_analysis_tool` in
`src/dbt/kipptaf/models/exposures/tableau.yml` and report its `depends_on`:

- `rpt_tableau__state_assessments_dashboard`
- `rpt_tableau__state_assessments_dashboard_comps`

For which of the six Tableau views reads which of those two, use the table in
the reference doc. `rpt_tableau__state_testing_accomodations` is a **different**
workbook — do not pull it in.

---

## Procedure: A student's score is missing from the dashboard

Almost always an unresolved `localstudentidentifier`.

1. **Confirm the score reached the warehouse.** Query
   `int_pearson__all_assessments` for the student, by `statestudentidentifier`
   rather than by local id — the local id is the thing under suspicion.
2. **Check whether the detector already flags it.** Run
   `test_incorrect_student_number_pearson`. Its failure rows carry
   `studenttestuuid`, both identifiers, the name and the test code. Whether
   `localstudentidentifier` is null is what tells you the mode; the test code
   tells you the assessment.
3. **Read which failure mode it is** — they need different fixes:

   | Symptom                                  | Mode              | Fix                 |
   | ---------------------------------------- | ----------------- | ------------------- |
   | `localstudentidentifier` null            | absent            | crosswalk sheet row |
   | `localstudentidentifier` present, wrong  | present-but-wrong | crosswalk sheet row |
   | no enrollment for that year and district | unmatchable       | **not the sheet**   |

   **Classify by mode, not by vendor.** Either vendor can produce either mode.
   Today's failures happen to split cleanly -- Pearson wrong, Cambium absent --
   but the Cambium reading is one administration's worth of data and is not a
   property of the vendor. See the reference doc.

   The absent mode is recoverable from `statestudentidentifier` and there is a
   standing recommendation to automate it. The present-but-wrong mode never is,
   so the sheet is permanent either way.

   **A wrong identifier that is itself a valid `student_number` will not show up
   here at all.** The join succeeds against the wrong student and the detector
   stays silent. If someone reports a score attached to the wrong kid, that is
   this, and no test will find it for you.

   **Before writing any row, confirm the student has an enrollment in the test's
   own academic year and district.** The sheet only overrides the identifier;
   the join still needs year and district to match an enrollment with
   `rn_year = 1`. If there is no such enrollment, a sheet row changes nothing
   and becomes permanent dead weight. This is the unmatchable category and it is
   an Ops question, not a sheet one -- see the reference doc. Check the academic
   year before spending time on it: the dashboard publishes a rolling window, so
   a flagged row old enough to fall outside it is not worth chasing.

   ```sql
   select academic_year, _dbt_source_project, student_number
   from `teamster-332318`.kipptaf_powerschool.base_powerschool__student_enrollments
   where student_number = <candidate> and rn_year = 1
   order by academic_year
   ```

   A name that resolves only when you search across other years or districts is
   the signature of this category, not a lead.

4. **Add the sheet row.** Sheet `1BubU91_j6jrmi6DC0A9QilwPQy0gZZMkvmQ6bifkKsM`,
   named range `src_pearson__student_crosswalk`. Two columns:

   | Column              | Value                              |
   | ------------------- | ---------------------------------- |
   | `Student_Test_UUID` | from the failure row, verbatim     |
   | `Student_Number`    | the correct network student_number |

   The sheet is named for Pearson but serves every NJ vendor. **Cambium
   corrections go in this same tab** -- `int_pearson__all_assessments` aliases
   Cambium's `student_test_uuid` to `studenttestuuid` before the join, so it
   reaches them with no code change. One row per test, not per student: a
   student with four bad test rows needs four rows here.

5. **Re-check by reading the sheet external directly**, with a Python client on
   ADC — the BigQuery MCP 403s on a Drive-backed external but ADC has Drive
   scope, and this reads the sheet live with no build:

   ```python
   client.query('''
     select count(*) as crosswalk_rows
     from `teamster-332318`.kipptaf_google_sheets.src_google_sheets__pearson__student_crosswalk
   ''')
   ```

   Confirm the row count rose by what you added, then re-run the detector once
   the models rebuild. **Never judge the sheet's current contents from the prod
   `stg_` table** — that is a table frozen at the last prod build, not a live
   read, so it reports pre-edit values indefinitely.

**Do not quote the student's name in a PR, issue, or Slack.** Quote the UUID.

---

## Procedure: Generate crosswalk rows for every flagged test

Use this instead of resolving rows one at a time when the detector has a batch
outstanding. The logic lives in
[`src/dbt/kipptaf/analyses/state_assessment_tiered_crosswalk_match.sql`](../../../src/dbt/kipptaf/analyses/state_assessment_tiered_crosswalk_match.sql);
this is the runbook. It is modelled on `collegeboard-ap-data-ingest-protocol`,
which solves the same problem for AP.

**PII.** Output carries names, dates of birth and student numbers. Terminal and
local scratch only -- never a PR, issue, commit or any file under version
control. Write results to a file and report only counts.

### What the rules require

Three criteria, in the order they bind:

1. **Enrollment gate, hard, every tier.** The candidate must have an enrollment
   row for the test's own `academic_year` and `_dbt_source_project` with
   `rn_year = 1`. Without it the sheet cannot help at all -- see the unmatchable
   category above.
2. **Grade corroboration.** Codes ending `03`-`08` encode the grade, so
   enrollment `grade_level` must equal it: a **hard gate**, mismatch routes to
   `flagged_for_review`. HS codes (`ALG01`, `ALG02`, `GEO01`, `ELA09`, `ELA10`,
   `ELAGP`, `MATGP`, `SCI11`) do not encode grade -- students sit Algebra I in
   grade 8 or 9 and the pathway tests in 11 -- so there it is **informational
   only and never gates**.
3. **Identity**: state id, first name, last name, date of birth.

| tier | identity evidence                               | note                                 |
| ---- | ----------------------------------------------- | ------------------------------------ |
| A    | state id + first + last + DOB                   | strongest                            |
| B    | state id + first + last, no usable DOB          | weakest auto-resolving tier          |
| C    | DOB + first + last, state id does **not** match | catches a wrong state id             |
| D    | DOB + last, first differs                       | nicknames; never auto-resolved alone |

**DOB is not available everywhere, and that is not a vendor property.**
`stg_pearson__njsla` / `_njsla_science` / `_parcc` carry `birthdate` only
because they `select * except (...)`, so it rides through unnamed.
`stg_cambium__njgpa` and `stg_pearson__njgpa` use explicit column lists that
omit it, though the raw files have it. Cambium therefore runs on Tier B. Adding
`birth_date` to the cambium package staging model would lift it to Tier A; that
is a package column add and needs the cross-project staging dance.

### Steps

1. **Count first.** Run the detector and report how many rows are outstanding,
   split by mode. Ask before running the match.
2. **Compile and run:**

   ```bash
   uv run dbt compile --project-dir src/dbt/kipptaf --target prod \
     --select "path:analyses/state_assessment_tiered_crosswalk_match.sql"
   ```

   Then execute the compiled SQL. Write the result to a local CSV rather than
   printing it -- 36-character UUIDs also trip the output scanner, so a printed
   result often comes back redacted anyway.

3. **Report the bucket split** -- `resolved`, `flagged_for_review`, `ambiguous`,
   `no_match` -- and the tier distribution. Ask before handing over rows.
4. **Deliver `resolved` in batches of 20**, as a plain two-column delimited
   block inside a fenced code block, `Student_Test_UUID` then `Student_Number`,
   so it pastes into two sheet columns without markdown pipes riding along. Wait
   after each batch. Never dump every batch at once.
5. **Present `flagged_for_review` separately**, as a table for individual
   decisions -- never in a paste block. These are grade-gate failures and
   Tier-D-only matches.
6. **Present `no_match` separately** and say which kind: no enrollment that year
   (unmatchable, not a sheet problem) versus enrolled but no tier satisfied.
7. **Present `ambiguous` separately**, as a table, never in a paste block. These
   rows carry **no** `proposed_student_number` on purpose — more than one
   student satisfied a tier, and the query withholds the candidate rather than
   emitting an arbitrary one. A person picks among the candidates or decides
   none of them fit. Never guess, and never default to the first.
8. **Audit after the paste.** See below.

### Procedure: Audit the crosswalk against the rules

Replays every existing sheet row through the tiers using its raw pre-repair
identifier and compares the rules' pick to what a human entered. Run it after
any batch of entries, and periodically.

Outcomes: `agrees`, `ambiguous`, `no_pick_identity`, `no_pick_not_enrolled`, and
`DISAGREES`.

**A disagreement is serious** -- it means a sheet row points at a different
student than the evidence supports. Investigate before assuming the rules are
wrong; the sheet has no test protecting it.

The 2026-09-17 baseline was 81 rows: 66 agree, 2 ambiguous, 7
`no_pick_identity`, 6 `no_pick_not_enrolled`, **0 disagreements**. The reference
doc carries the interpretation. Compare against that baseline rather than
treating any non-agreeing row as new.

Resist adding a tier to absorb `no_pick_identity` rows. A new tier is justified
only by a deterministic, generalizable pattern, the same bar the AP protocol
sets for its no-match bucket -- otherwise the rules drift toward rubber-stamping
whatever is already in the sheet, which destroys their value as an independent
check.

---

## Procedure: Bootstrap comps rows from a screenshot

The November problem. Official comparison files do not arrive until roughly
November, so until then the figures come out of NJDOE and district
presentations. The user pastes an image; you emit paste-ready rows.

### Step 1 — establish what the image is, before reading any number

Ask, and do not guess:

- Which **academic year**, in starting-year form. A deck labelled "Spring 2025
  results" is `academic_year = 2024`.
- Which **region** the comparison is for.
- Which **comparison entity** — `City`, `State`, or `Neighborhood Schools`.
  Neighborhood Schools is Miami only.
- Whether the figures are **percent proficient**, and whether a **denominator**
  (tested students) is shown.

**A missing denominator is normal for a media source and is not a reason to
stop.** Leave `total_students` empty and load the percentage. Never invent a
denominator -- it feeds `total_proficient_students` and the weighted ALG01
rollup, and a fabricated one corrupts both silently.

Say out loud what the empty denominator costs, because it is not visible
anywhere: the row will populate the five views fed by the `state_comps` CTE,
which reads `avg(percent_proficient)` directly, and will arrive in **Advanced
Comps with a NULL percentage**, because that model recomputes
`safe_divide(sum(proficient), sum(total))`. Verified against production. The row
is present and the number is gone.

### Step 2 — read the image, and show your reading before emitting rows

Echo back a plain table of exactly what you extracted — test or grade label,
subgroup, percent, denominator — and say which cells you were unsure of. A
misread percentage becomes a comparison nobody ever audits. This step is not
optional just because the user asked for rows.

### Step 3 — derive the row metadata rather than asking for it

`aligned_test_code` is the key everything else follows from:

| Test code       | `school_level` | `grade_range_band` | `discipline`     |
| --------------- | -------------- | ------------------ | ---------------- |
| `ELA03`–`ELA04` | `ES`           | `3-8`              | `ELA`            |
| `ELA05`–`ELA08` | `MS`           | `3-8`              | `ELA`            |
| `ELA09`,`ELA10` | `HS`           | `HS`               | `ELA`            |
| `ELAGP`         | `HS`           | `HS`               | `ELA`            |
| `MAT03`–`MAT04` | `ES`           | `3-8`              | `Math`           |
| `MAT05`–`MAT08` | `MS`           | `3-8`              | `Math`           |
| `MATGP`         | `HS`           | `HS`               | `Math`           |
| `ALG01`         | `MS` and `HS`  | `HS`               | `Math`           |
| `ALG02`,`GEO01` | `HS`           | `HS`               | `Math`           |
| `SCI05`,`SCI08` | `MS`           | `3-8`              | `Science`        |
| `SCI11`         | `HS`           | `HS`               | `Science`        |
| `SOC08`         | `MS`           | `3-8`              | `Social Studies` |

`assessment_name` follows region and discipline:

| Region                   | Discipline         | `assessment_name`               |
| ------------------------ | ------------------ | ------------------------------- |
| Newark, Camden, Paterson | ELA, Math          | `NJSLA`                         |
| Newark, Camden, Paterson | ELA/Math, GP codes | `NJGPA`                         |
| Newark, Camden, Paterson | Science            | `NJSLA Science`                 |
| Miami                    | ELA, Math          | `FSA` to AY2021, `FAST` AY2022+ |
| Miami                    | Science            | `Science`                       |
| Miami                    | Social Studies     | `EOC`                           |

**`assessment_name` stays `NJGPA` for Cambium-era rows.** The Cambium staging
model sets `assessment_name = 'NJGPA'` and distinguishes the vendor on
`assessment_version = 'NJGPA-A'`. The comps join keys on `assessment_name`, so
writing `NJGPA-A` here silently matches nothing.

`season` is always `Spring`.

### Conventions specific to a media-sourced load

- **`Total` / `All Students` only.** Press figures carry no demographic
  breakouts. One row per test code per region; subgroups wait for the official
  file.
- **ALG01 comes mixed and is written to both levels.** Media never separates
  Algebra I taken in middle school from high school. Write the same published
  figure to both the `MS` and `HS` `school_level` rows, `remove_row = FALSE` on
  both. Known to be imprecise; the weighted rollup `remove_row` exists for needs
  counts, which an interim load does not have. Corrected when the official file
  lands.
- **Report, do not adjudicate.** Load what the state published. A redesigned
  assessment, a vendor change, or a year-over-year swing that looks implausible
  is worth _mentioning_ to the requester, but it is not a reason to withhold,
  smooth or footnote the figure in the sheet. We do not make the rules of
  comparison.
- **`assessment_name` stays `NJSLA` for Cambium-era NJSLA.** The Spring 2026
  administration is Cambium's redesigned form, but the vendor form lives in
  `assessment_version` (`NJSLA-A`, mirroring `NJGPA-A`) on the score side, and
  the comps join keys on `assessment_name`. Writing a version string into the
  sheet's `assessment_name` matches nothing.
- **`Neighborhood Schools` is Miami only.** A NJ statewide figure is
  `comparison_entity = 'State'`, written once per NJ region -- Camden, Newark
  and Paterson each get their own row, because the sheet is region-grained.

### Step 4 — map the demographic vocabulary

`comparison_demographic_group` is determined by the subgroup:

| Group                 | Subgroups                                                                                                              |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `Total`               | `All Students`                                                                                                         |
| `Gender`              | `Female`, `Male`                                                                                                       |
| `Aggregate Ethnicity` | `African American`, `American Indian`, `Asian`, `Hispanic`, `Native Hawaiian`, `Other`, `White`                        |
| `Subgroup`            | `Economically Disadvantaged`, `Non Economically Disadvantaged`, `ML`, `Students With Disabilities`, `SE Accommodation` |

**Use exactly these spellings.** The source deck will say things like "Black or
African American", "Econ. Disadvantaged", "SWD", "ELL". Translate. The staging
model rewrites two historical variants for backward compatibility, but an
`accepted_values` test at `severity: error` rejects anything outside the list —
and the reason that test exists is that a spelling variant entered for AY2024
silently zeroed every Black/African American comparison in NJ. See the reference
doc's "Resolved" section.

### Step 5 — emit rows in sheet column order

Fourteen columns, in this order. Emit them as a tab- or comma-separated block
the user can paste directly:

| #   | Column                            | Notes                                  |
| --- | --------------------------------- | -------------------------------------- |
| 1   | `academic_year`                   | integer, starting year                 |
| 2   | `assessment_name`                 | per the table above                    |
| 3   | `season`                          | `Spring`                               |
| 4   | `school_level`                    | per test code                          |
| 5   | `grade_range_band`                | per test code                          |
| 6   | `discipline`                      | per test code                          |
| 7   | `aligned_test_code`               |                                        |
| 8   | `region`                          | Newark / Camden / Miami / Paterson     |
| 9   | `comparison_entity`               | City / State / Neighborhood Schools    |
| 10  | `comparison_demographic_group`    | per the vocabulary table               |
| 11  | `comparison_demographic_subgroup` | per the vocabulary table               |
| 12  | `percent_proficient`              | **decimal fraction, not a percentage** |
| 13  | `total_students`                  | integer denominator                    |
| 14  | `remove_row`                      | `FALSE`, except the ALG01 case below   |

`percent_proficient` is a fraction. A deck showing 42% is `0.42`. Getting this
wrong inflates every comparison by 100x and the aggregates still compute
cleanly, so nothing fails.

**The ALG01 exception.** Official sources publish ALG01 demographic breakdowns
only for grades 8+ combined, while overall comparisons split MS from HS. Enter
HS-only ALG01 rows with `remove_row = TRUE`, `school_level = HS` and
`grade_range_band = HS`. The staging model filters them out of the main branch
and re-aggregates them into a single weighted `Total` / `All Students` row.
Never set `remove_row = TRUE` on anything else.

### Step 6 — audit after the paste, before telling anyone it is done

**Read the sheet external directly. Do not build anything.** The BigQuery MCP
service account has no Drive scope and 403s on a sheet-backed external, but ADC
does, so a Python client queries the live sheet — no dbt build, no
`stage_external_sources`, and the answer reflects the paste seconds after it
happens. A `--target staging` build is a shared write needing authorization, and
the copy it makes is frozen at build time, so it cannot answer "did my paste
land" anyway.

```python
# uv run python <script.py>
from google.cloud import bigquery

client = bigquery.Client(project="teamster-332318")
rows = list(client.query('''
  select
    countif(academic_year = <year>) as rows_entered,
    count(distinct if(academic_year = <year>, aligned_test_code, null)) as test_codes,
    count(distinct if(academic_year = <year>, region, null)) as regions,
    countif(academic_year = <year> and percent_proficient > 1) as pct_over_one,
    countif(academic_year = <year> and percent_proficient is null) as pct_null,
    countif(academic_year = <year> and total_students is not null) as has_denominator,
    countif(academic_year = <year>
            and comparison_demographic_subgroup != 'All Students') as not_all_students,
    min(if(academic_year = <year>, percent_proficient, null)) as min_pct,
    max(if(academic_year = <year>, percent_proficient, null)) as max_pct,
    count(*) as sheet_rows_total
  from `teamster-332318`.kipptaf_google_sheets.src_google_sheets__state_test_comparison_demographics
''').result())
```

What each answer has to be:

- **`pct_over_one` must be 0.** Anything else is the percentage-entered-as-a-
  -percentage mistake, which computes cleanly and inflates every comparison
  100x.
- **`min_pct` / `max_pct` must bracket the source figures.** Cheap catch for a
  column-offset paste.
- **`rows_entered` must equal what you generated**, and `sheet_rows_total` must
  have grown by exactly that much — a short count means the paste truncated.
- **`has_denominator` will be 0 for a media load.** Expected, not a fault.
- **`not_all_students` must be 0** for a media load.

Also check the whole sheet for duplicate keys, since the uniqueness test fires
at build time rather than at paste time:

```sql
select count(*) from (
  select academic_year, aligned_test_code, school_level, region, comparison_entity,
         comparison_demographic_group, comparison_demographic_subgroup
  from `teamster-332318`.kipptaf_google_sheets.src_google_sheets__state_test_comparison_demographics
  group by 1,2,3,4,5,6,7
  having count(*) > 1
)
```

Compare `rows_entered` and `test_codes` against the prior year for the same
region and entity. A large drop means the source covered fewer test codes than
the official file will, which is expected for an interim load but should be said
out loud so it gets replaced.

Finally confirm the comparisons actually resolve — a row that finds no Region
partner reads `false`, indistinguishable from a genuine loss:

```sql
select comparison_entity, comparison_demographic_subgroup,
       count(*) as n, countif(region_outperformed) as outperformed
from `teamster-332318`.kipptaf_tableau.rpt_tableau__state_assessments_dashboard_comps
where academic_year = <year> and region = '<region>'
group by 1, 2
order by 1, 2
```

A subgroup with `n > 0` and `outperformed = 0` across every test code is the
signature of a vocabulary mismatch, not of poor performance. Check the spelling
before reporting the result.

### Step 7 — say plainly that the data is provisional

Bootstrapped figures are transcribed from a presentation, not from an official
file. Tell the user which rows are provisional and that they are to be replaced
when the official comparison file lands.

---

## Procedure: Replace interim comps with the official file

**First decide which job this is.** Adding a year the sheet does not yet carry
is an append: there are no keys to collide with, nothing to remove, and the
uniqueness test protects you. Replacing a year that already has rows is the full
swap below. Check before touching anything:

```sql
select academic_year, comparison_entity, count(*) as rows_present
from `teamster-332318`.kipptaf_google_sheets.stg_google_sheets__state_test_comparison_demographics
where academic_year = <year>
group by 1, 2
```

Empty result means append. Anything else means swap.

When the official comparison data arrives for a year already present, **replace
the entire contents of the tab, not the interim rows individually.** Surgical
row-level replacement means matching seven key columns by hand across hundreds
of rows, and a single missed row leaves a press figure sitting among official
ones with nothing marking it. A full swap is both easier and safer.

1. **Build the complete replacement set first**, covering every academic year
   the sheet should carry, not only the new one. The official file is the
   authority for its own year; prior years come from the current sheet.
2. **Snapshot what is there before overwriting.** Query the staging model and
   keep the result locally. A Google Sheets paste is not easily undone, and the
   external table reads the sheet live, so a bad paste is visible downstream
   almost immediately.
3. **Clear the range and paste the full set.** Do not append. The sheet carries
   a `dbt_utils.unique_combination_of_columns` test over seven columns, so a
   duplicated key fails the build rather than silently double-counting — but a
   **stale row that the new set simply omits is caught by nothing.** That
   asymmetry is the reason for the full swap.
4. **Rebuild and run the Step 6 audit**, then diff `percent_proficient` for the
   replaced year against what was there before, and report any figure that moved
   materially. An interim figure that was transcribed wrong and has since been
   quoted is worth naming out loud rather than quietly correcting.
5. **Confirm the denominators arrived.** Counts are the point of the official
   file. If `total_students` is still empty after the swap, the rows are interim
   in everything but name, and Advanced Comps is still showing a percentage with
   nothing behind it.

---

## Procedure: Verify a comps model change against production

Run this for any change to `rpt_tableau__state_assessments_dashboard_comps` or
its upstreams. The model feeds a dashboard people quote in meetings, and the
interesting failure is not an error -- it is a value quietly moving on a row
nobody was looking at.

Compile the model, then compare the compiled SQL against the production
relation. Four rules, each of which exists because the obvious version of the
check is blind to something:

1. **Confirm the projected key is unique on both sides before joining.** The
   final `SELECT` does not project `focus_level` even though `grouped_comps`
   groups on it, so duplicate projected keys are possible in principle. If the
   key is not unique the join fans out and every count below is meaningless.
   Compare `count(*)` against `count(distinct format('%T', (<key columns>)))` on
   each side.
2. **Full outer join, never inner.** An inner join cannot see a row that
   appeared or vanished -- exactly the damage a bad `GROUP BY` or a lost union
   branch does. Count `rows_only_in_prod` and `rows_only_in_new` explicitly and
   expect zero of each.
3. **Compare every value column with `IS DISTINCT FROM`, not `!=`.** `!=` is
   null-blind: `null != 0.42` is null, not true, so a row whose value appeared
   or disappeared passes silently. Since null-to-value is the most common
   deliberate change here, `!=` would hide the very thing being verified.
4. **Separate "a null became a value" from "an existing value moved."** These
   are different events and lumping them loses the signal. A dedicated counter
   for `p.percent_proficient is not null and n.<col> is distinct from p.<col>`
   is the one that must read zero unless the change was meant to restate
   existing figures.

Value columns to cover, all six: `percent_proficient`, `total_students`,
`total_proficient_students`, `region_matched`, `region_outperformed`,
`region_matched_or_outperformed`. Omitting a column means not verifying it; say
which ones were compared rather than implying all of them.

Worked example, the 2026-09-17 percentage fallback: 13,897 rows both sides,
13,897 distinct keys both sides, 0 rows on either side alone, 12 rows null to
value, **0 existing values moved**, `total_students` and
`total_proficient_students` unchanged, and 2 each on `region_outperformed` and
`region_matched_or_outperformed` because a recovered percentage can now
participate in the Region self-join. `region_matched` stayed at 0, which is the
right shape -- exact equality was never going to newly fire.

Expect knock-on changes in the three booleans whenever a percentage changes, and
say so up front. A reviewer who is told only about the percentages will read a
moved boolean as an unexplained regression.

---

## Procedure: A comparison reads false, or a comp is missing

Work in this order.

1. **Is the comparison entity present for that region?** `Neighborhood Schools`
   is Miami only. NJ regions have `City` and `State` only.
2. **Is the subgroup spelling canonical?** The single most common cause. Query
   the distinct `comparison_demographic_subgroup` values in
   `rpt_tableau__state_assessments_dashboard_comps` for the region and year, and
   compare against the Step 4 vocabulary. A value outside it finds no Region
   partner and every comparison reads `false`.
3. **Does a Region partner row exist at all?** About 4,000 rows, a third of all
   non-Region rows, have no partner — overwhelmingly subgroups KTAF has no
   students in. **That is the expected state, not a bug**, and it does not
   surface as a wrong number: Advanced Comps lays the entities out as columns,
   so a missing Region is simply an empty cell. It bites only through the
   `region_outperformed` quick filter, which cannot tell a real loss from an
   absent comparison. Read the reference doc before investigating.

   When diagnosing, relax one join column at a time instead of guessing. Nine
   view-expanding subqueries exceed BigQuery's query-planning limit, so pull the
   view once into memory and do it there — roughly 14,000 aggregate rows, no
   PII.

4. **Is the year in the sheet at all?** Comparison data stops at
   `academic_year = 2024`. NJ has no 2019 or 2020 rows, and Paterson starts
   at 2023.
5. **Is it the wrong comps path?** If the number in question is on Overview,
   Landing Page, Demographics, Proficiency YoY or Teacher/Student Roster, it
   came from the `state_comps` CTE — Total / All Students only, pivoted wide —
   not from the comps model. Debug the CTE, not the view.

---

## Procedure: Academic year rollover

After `current_academic_year` bumps in July:

- `rpt_tableau__state_assessments_dashboard` filters scores to
  `current_academic_year - 7`, so history rolls off the back automatically. No
  toggle to flip.
- The **schedules** CTEs read `current_academic_year` for teacher attribution.
  Before the new year's PowerSchool sections exist, `school_current` /
  `teacher_name_current` come back null on the roster views. Expected, not a
  bug.
- The **preliminary-score branch** self-deactivates: it is gated on
  `valid_prelim_assessments`, which drops an assessment once official scores for
  that year land in `int_pearson__all_assessments`. Do not comment it in or out
  by hand; that gating was built specifically to remove that chore.
- Comparison data for the new year will not exist. Expect the comps views to be
  empty for it until either a bootstrap or the official file lands.

---

## Gotchas

- **Never judge the current contents of either Google Sheet from the prod `stg_`
  table.** Both are frozen at the last prod build. Rebuild into dev.
- **The BigQuery MCP cannot read either sheet's external table** — the service
  account has no Drive scope and returns 403. Build the staging model first,
  then query the materialized table.
- **The Tableau MCP cannot answer "what does the workbook do with this field".**
  It is read-only, returns no calculated-field text, and 500s on
  `get-datasource-metadata` for the embedded extracts this workbook uses. Use
  the `tableau-workbook-xml` skill to download and inspect the `.twb`.
- **`rpt_tableau__state_testing_accomodations` is not part of this dashboard.**
  Similar name, different workbook.
- **Cambium and Pearson aligned columns are maintained in two separate
  packages** and cannot share code. Changing a band, label, or mapping in one
  means changing it in the other. See the reference doc.
