# The comps sheet: interim and official loads

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

Say out loud what the empty denominator costs. The percentage reaches every
view: the `state_comps` CTE reads `avg(percent_proficient)` directly, and
`rpt_tableau__state_assessments_dashboard_comps` falls back to the reported
percentage when a group has a single source row (every group today). What is
lost is the counts: `total_students` and `total_proficient_students` stay empty,
and the weighted ALG01 rollup cannot use the row.

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
| `ALG01` (MS)    | `MS`           | `3-8`              | `Math`           |
| `ALG01` (HS)    | `HS`           | `HS`               | `Math`           |
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

**`assessment_name` stays `NJGPA` for Cambium-era rows.** The cambium package
`int_cambium__all_assessments` sets `assessment_name = 'NJGPA'` on Cambium NJGPA
rows and distinguishes the form on `assessment_version = 'NJGPA-A'`. The comps
join keys on `assessment_name`, so writing `NJGPA-A` here silently matches
nothing.

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
- **`assessment_name` stays `NJSLA` for Cambium-era NJSLA.** Cambium NJSLA rows
  carry `NJSLA` (or `NJSLA Science`) in both `assessment_name` and
  `assessment_version`; only NJGPA has a separate Cambium version. The comps
  join keys on `assessment_name`, so any other string in the sheet's
  `assessment_name` matches nothing.
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
silently zeroed every Black/African American comparison in NJ. See the doc's
_Controlled vocabulary_ section.

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

**Read the sheet external live through ADC**
(`.claude/context/claude_ai_Google_Cloud_BigQuery.md`). Do not build anything: a
`--target staging` build is a shared write needing authorization, and its copy
is frozen at build time.

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
