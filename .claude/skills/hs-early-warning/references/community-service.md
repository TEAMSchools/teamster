# Community service

`rpt_tableau__community_service` feeds the Community Service tab. This file is
enough to diagnose any hours question; do not open the reference doc or
`yearly-upkeep.md` for one.

## Grain and scope

One row per student per DeansList community service entry (`dl_said`), tested by
`unique_combination_of_columns` on `student_number`, `dl_said`. A student with
no entries this year appears once, with a null `dl_said`. Several entries with
the same date and behavior are separate real entries, not a fan-out.

Scope: the current academic year, `rn_year = 1`, `enroll_status = 0`, grade 9
and up. Unlike the early warning extract, Miami Tech is included. Entries must
fall inside that one enrollment's dates, so hours logged during an earlier stint
the same year (a mid-year transfer) do not show.

## Two measures of hours

| Column                             | Source                                                                                                              | Covers                   |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------ |
| `cs_hours`                         | `stg_deanslist__behavior`, behavior categories `Community Service` and `Community Service Hours`                    | this year, per entry     |
| `grade_9_hours` … `grade_12_hours` | DeansList student custom fields `9th_hours` … `12th_hours`, through `int_deanslist__students__custom_fields__pivot` | earlier years, per grade |

`cs_hours` is the leading digits of the behavior name, parsed in
`stg_deanslist__behavior` (`regexp_extract(behavior, r'^\d+')`). Today's names
are `1 hour`, `5 hours` and `10 hours`. A name that does not start with a number
(`Half hour`, `Community Service - 5 hours`) parses to null and the extract's
`coalesce` turns it into 0: the student's hours go missing with no error.

The custom-fields join is on `student_school_id` only, with no region key. The
package model is unique per region and the union is unique network-wide today;
adding the region key would drop prior-year hours for a student who moved
between regions, so it was left off deliberately.

Tableau adds the two, per student:

```text
Total (Prev Years)             = {FIXED [Student Number] : MAX(g9 + g10 + g11 + g12)}
LOD Student Hours Current Year = {FIXED [Student Number] : SUM([Cs Hours])}
LOD Total All Years            = current year + previous years
```

Grad Goal Met is that total at or above 50. Early in the year the total is
almost all prior years, so a missing upload shows as a whole grade's hours
dropping to zero, while a bad behavior name shows as scattered students losing
this year's hours.

## The yearly upload

The custom fields hold last year's behavior-log totals. Measured 2026-09-30: for
about 96% of students who logged hours in AY2025-26, the custom field for last
year's grade equals the sum of last year's `cs_hours`. So someone totals last
year's entries per student at rollover and writes them into DeansList. Jabari
does it; the exact steps are not written down anywhere.

`rpt_gsheets__community_service_upload` (disabled, no exposure) computes that
upload: current and prior year, grades 9-12, hours pivoted into `HOURS-9TH` …
`HOURS-12TH` keyed by `StudentID`. It still uses the old parse
(`left(behavior, length(behavior) - 5)`), not the staging model's `cs_hours`.
Before re-enabling it, confirm with Jabari that it matches what he uploads, and
switch it to `b.cs_hours`.

Questions for Jabari, not yet answered:

1. Do you upload last year's totals into the grade custom fields each summer or
   fall? From what file?
2. Is the upload additive (adds to the field) or a replacement?
3. What happens to a student who transferred in with outside hours?

Record the answers in the doc's _Start-of-year procedure_, Step 2, and here.

## QA after the upload

For current 10th to 12th graders who logged hours last year, compare last year's
grade custom field with the sum of last year's `cs_hours` (join last year's
`int_extracts__student_enrollments` stint to `stg_deanslist__behavior` on
`student_school_id`, `_dbt_source_project` and the stint dates). Report the
share that match, per grade. A grade near zero means the upload has not
happened.
