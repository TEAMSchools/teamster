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

- `academic_year` is the STARTING year. Spring 2025 testing is
  `academic_year = 2024`. Confirm with the user before generating any row.
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
   and becomes permanent dead weight. This is the unmatchable category, it is
   currently 8 of 20 outstanding rows, and it is an Ops question -- see the
   reference doc.

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
   corrections go in this same tab** -- `stg_cambium__njgpa` aliases
   `student_test_uuid` to `studenttestuuid` upstream, so the join reaches them
   with no code change. One row per test, not per student: a student with four
   bad test rows needs four rows here.

5. **Rebuild and re-check.** Google Sheets externals read live, so rebuilding
   the staging model into your dev schema picks up the edit with no
   `stage_external_sources`:

   ```bash
   uv run dbt build \
     --select stg_google_sheets__pearson__student_crosswalk \
     --project-dir src/dbt/kipptaf --target dev --defer --state target/prod
   ```

   Then re-run the detector and confirm the row is gone. **Never judge the
   sheet's current contents from the prod `stg_` table** — it is frozen at the
   last prod build.

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
| B    | state id + first + last, DOB unavailable        | Cambium; strong, not conclusive      |
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

3. **Report the bucket split** -- `resolved`, `flagged_for_review`, `no_match`
   -- and the tier distribution. Ask before handing over rows.
4. **Deliver `resolved` in batches of 20**, as a plain two-column delimited
   block inside a fenced code block, `Student_Test_UUID` then `Student_Number`,
   so it pastes into two sheet columns without markdown pipes riding along. Wait
   after each batch. Never dump every batch at once.
5. **Present `flagged_for_review` separately**, as a table for individual
   decisions -- never in a paste block. These are grade-gate failures and
   Tier-D-only matches.
6. **Present `no_match` separately** and say which kind: no enrollment that year
   (unmatchable, not a sheet problem) versus enrolled but no tier satisfied.
7. **Audit after the paste.** See below.

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
- Whether the figures are **percent proficient** and whether a **denominator**
  (tested students) is shown. Both columns are required.

If a denominator is absent, stop and say so. `total_students` feeds
`total_proficient_students` and the weighted ALG01 rollup; inventing it corrupts
both.

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

Rebuild into dev and check the grain and the plausibility of the values:

```bash
uv run dbt build \
  --select stg_google_sheets__state_test_comparison_demographics \
  --project-dir src/dbt/kipptaf --target dev --defer --state target/prod
```

Then, against the rebuilt `zz_<user>_kipptaf_google_sheets` copy:

```sql
select
  academic_year, region, comparison_entity,
  count(*) as rows_entered,
  count(distinct aligned_test_code) as test_codes,
  countif(percent_proficient > 1) as pct_over_one,
  countif(percent_proficient is null or total_students is null) as missing_values,
  min(percent_proficient) as min_pct,
  max(percent_proficient) as max_pct
from <rebuilt table>
where academic_year = <year>
group by 1, 2, 3
order by 1, 2, 3
```

`pct_over_one` must be 0 — anything else is the percentage-versus-fraction
mistake. Compare `rows_entered` and `test_codes` against the prior year for the
same region and entity; a large drop means the deck covered fewer test codes
than the official file will, which is expected for a bootstrap but should be
stated to the user so it is replaced in November.

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

## Procedure: Replace bootstrapped rows with the official file

When the official comparison data arrives:

1. Identify the provisional rows — same `academic_year`, `region` and
   `comparison_entity` as the bootstrap.
2. Replace rather than append. The sheet has a
   `dbt_utils.unique_combination_of_columns` test on seven columns including
   year, test code, school level, region, entity, group and subgroup; appending
   a second copy fails it.
3. Rebuild and re-run the Step 6 audit, then diff `percent_proficient` against
   the provisional values and report any figure that moved materially. A
   transcription error that survived into a board conversation is worth naming.

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
3. **Does a Region partner row exist at all?** Self-join the view to itself on
   the ten keys — year, school level, grade range band, assessment name,
   discipline, test code, region, demographic group, demographic subgroup —
   filtering `b.comparison_entity = 'Region'`, and count the nulls. **195 rows
   network-wide currently have no partner even with canonical spelling**, and
   573 of 870 `Neighborhood Schools` rows have none; see the reference doc's
   open issue before treating a null as new.
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
