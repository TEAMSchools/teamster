# Student persistence model — design

Refs [#6195](https://github.com/TEAMSchools/teamster/issues/6195).

Status: proposal for team review. Nothing is built yet.

## Summary

We propose a single Tableau reporting view, `rpt_tableau__student_persistence`,
to drive a new, simpler student persistence dashboard. The view replaces the Ops
Dashboard's "Attrition Analysis - Reasons" tab as the source for student
persistence reporting.

The case for a separate view:

- **Enrollment reporting is moving.** A new ADE dashboard is being built to take
  over the Ops Dashboard's enrollment and ADE reporting. One all-in-one
  reporting view made sense while a single workbook served enrollment and
  persistence. Persistence now needs a source built for it.
- **Tableau holds the key metrics today.** `rpt_tableau__ops_dashboard` is an
  enrollment roster. Tableau calculations on top of it decide who counts as
  attrition, which exit date and code apply, how codes group, and which year
  shows. No one can test those calculations, and any other report that needs
  persistence has to rebuild them.
- **Exit reasons have a new source.** Finalsite withdrawal forms are now the
  source of truth for exit reasons and categories, not PowerSchool or Focus. The
  Ops reporting view carries only the SIS exit fields.

In the new view, dbt makes every student-level judgment: `is_attrition`, the
persistence status, the exit reason and category, and when the student left. The
dashboard only counts, filters, and exports, so it stays simple and direct.

The dashboard answers 3 questions at the network, region, school, grade, IEP,
multilingual learner (ML), gender, and years-at-KIPP levels, with a student
roster export:

- How many students persisted, and what percent?
- Why did the others leave (exit category and exit reason)?
- When did they leave (mid-year, end of year, summer, or the start of the next
  year)?

Tableau reads one view. Behind that view, 2 intermediate dbt models do the work
(see _Design_), so each rule can be tested on its own.

## What exists today

### The Ops Dashboard tab

The tab reads `rpt_tableau__ops_dashboard`, which has one row per student per
year with next-year enrollment columns attached. Tableau calculations on top of
that view hold the persistence metrics:

- An `Attrition Status` calculation decides attrition from next-year enrollment
  and the PowerSchool "Graduated Students" school.
- "Most recent" calculations pick the exit date, exit code, and exit comment
  from this year's or next year's record.
- Groups sort exit codes into controllable and non-controllable, and into
  mid-year, end-of-year, and summer buckets.
- A filter selects the academic year.

### How the two sources compare

We compared the tab's 2025-26 numbers with the prototype below, student by
student. They agree on every student except 392 grade 12 graduates (Newark 298,
Camden 94). The tab counts those graduates as leavers because PowerSchool wrote
no next-year graduate record for them. A workbook change could close that gap,
and the new view handles graduates through its terminal-grade rule. The gap
matters mostly as a note for anyone who compares the 2 dashboards during the
switch.

### The 2025-26 prototype

A static 2025-26 persistence report already exists: the
[2025-26 Student Persistence report](https://claude.ai/artifact/9wQRjFLgVFNz6kEaCFkixk?sk=Mc8DrGDC2VSPgtHoKXqtdg#all)
(KTAF sign-in required). KTAF shared the report and used it for the TC, Region,
and DSO stepbacks on student persistence in October 2026. The report rolls up
hand-built views in the personal development dataset
`teamster-332318.ldesimon_dev`:

- `student_retention_base`: one row per student enrolled on October 1, with
  `is_retained`.
- `student_retention_rollups`: the same counts at 6 grains.
- `student_persistence_exit_reasons_audit` and
  `student_persistence_exit_reasons_roster`: exit reason and timing logic for
  each leaver.

Its numbers are the ones stakeholders hold today: 8,491 of the students enrolled
on October 1, 2025 persisted (79.8%), and 2,145 did not.

The logic is correct, and this design keeps it. The views cannot move to
production as they stand:

- **The year in progress breaks.** The 2027-28 grade list does not exist yet, so
  the views flag every 2026-27 student as in a terminal grade. Run today, they
  report 99.3% persistence (10,927 of 11,001), because they count students who
  are still enrolled as students who finished.
- **Dates are hard-coded.** The SQL types in October 1, 2025, July 1, 2026,
  September 30, 2026, and the first day of 2026-27.
- **The views are too heavy.** The stacked views already fail with BigQuery's
  "query is too complex," and each refresh needs a hand-rebuilt working table.
- **Nothing refreshes or tests them.** dbt and Dagster do not know the views
  exist.

### Other attrition definitions in the repo

2 other student attrition definitions run in production. This design does not
change them:

- `rpt_tableau__student_attrition_over_time`: weekly attrition for students who
  were enrolled on October 1 of the prior year and also have a current-year
  enrollment.
- `int_students__retention_over_time`, which feeds the topline Student Retention
  metric. It counts only graduates as completers, and the topline excludes
  Paterson.

## Approaches considered

- **A — focused models feeding 1 reporting view.** One table builds the
  population and outcome, a second adds exit reasons and timing, and a view
  joins them for Tableau. Each piece can be tested alone, and the tables keep
  BigQuery under its complexity limit.
- **B — port the prototype as 1 reporting model.** It is the fastest to write,
  but it brings back the complexity limit, cannot be tested in pieces, and
  buries the persistence definition where nothing else can reuse it.
- **C — add persistence columns to `rpt_tableau__ops_dashboard`.** It reuses an
  existing model, but it ties the 2 dashboards back together. That model also
  refreshes hourly and is due for a rebuild.

**Selected: A.**

## Decisions made in design

| #   | Decision                          | Choice                                                                                                                                       |
| --- | --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Students who join after October 1 | Include all of them, flagged, so the main metric ignores them and the dashboard can still show a late-joiner rate.                           |
| 2   | Years                             | The 2 most recent October 1 cohorts. The window moves on October 1, not July 1.                                                              |
| 3   | The year in progress              | `is_attrition` means "left so far." Students who have not left read "Active."                                                                |
| 4   | Model layout                      | 2 intermediate tables feed 1 reporting view. Tableau reads only the reporting view.                                                          |
| 5   | Exit reason source                | Finalsite or blank, for every year. No PowerSchool or Focus fallback.                                                                        |
| 6   | Reason codes and categories       | A KTAF-owned Google Sheet maps each Finalsite reason to a code, a category, and a controllable flag.                                         |
| 7   | Persistence scope                 | Each row answers one question: was this student enrolled on October 1 of the following year? Nothing about a student is global across years. |
| 8   | Roster columns                    | `student_name` is included. Ethnicity is left out.                                                                                           |

Finalsite answer overwrites (see _Open questions_) stay open.

## Design

### Models and data flow

```text
SIS enrollments ─┐
calendars ───────┼─> int_students__persistence ──────────────┐
grades offered ──┘   (population, outcome status)            │
                                                             ├─> rpt_tableau__student_persistence ─> Tableau
Finalsite form answers (4 regions) ──┐                       │
Finalsite status report ─────────────┼─> int_students__persistence_exits
exit reason crosswalk (Google Sheet) ┘   (reason, withdrawal date, timing)
```

| Model                              | Grain                               | Stored as | Job                                                                                                                                                                         |
| ---------------------------------- | ----------------------------------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `int_students__persistence`        | One row per student per cohort year | Table     | Builds the population (October 1 cohort and late joiners) and the outcome: status, `is_attrition`, the terminal-grade test, the October 1 and 15 flags, demographics.       |
| `int_students__persistence_exits`  | Same key, every row                 | Table     | Adds the exit reason, code, category, the raw Finalsite answers, the withdrawal date and its timing bucket, and `has_nonreturn_notice`. Blank where a student has not left. |
| `rpt_tableau__student_persistence` | Same key                            | View      | Joins the 2 tables. It enforces a contract and a uniqueness test, and it is the only model Tableau reads.                                                                   |

The intermediate models live in `src/dbt/kipptaf/models/students/intermediate/`
and the reporting view in `src/dbt/kipptaf/models/extracts/tableau/`. Storing
the 2 intermediate models as tables keeps BigQuery under its complexity limit.

Supporting changes:

- **Exit reason crosswalk.** A new Google Sheet source, staged as
  `stg_google_sheets__finalsite__exit_reason_crosswalk`. The FRESH dashboard's
  `stg_google_sheets__finalsite__status_crosswalk` is the precedent for a
  team-owned Finalsite mapping sheet.
- **Finalsite custom attributes, 4 regions.** The Finalsite package pivot
  `int_finalsite__contact_custom_attributes` reads only Miami's spelling of the
  notes field, `withdraw_reason_notes_txt`. New Jersey writes
  `withdrawal_reason_notes_txt`. The kipptaf union of that model covers Miami
  only today and needs Newark, Camden, and Paterson added.
- **Lineage.** A `tableau.yml` exposure for the new workbook.

### Population and outcome

**Window.** The model covers the 2 most recent cohort years whose October 1 has
passed. On October 30, 2026 those are 2025-26 and 2026-27. On October 1, 2027
the window becomes 2026-27 and 2027-28 without a code change. A July 1 roll
would drop the prior year exactly while the current cohort's summer leavers are
still arriving.

**Population, per cohort year.** Region, school, and grade come from the
student's last enrollment of that year (`rn_year = 1`), as in the prototype. In
2025-26, only 14 students changed schools after October 1.

| Group            | Rule                                                                            | `counts_toward_oct01_persistence` |
| ---------------- | ------------------------------------------------------------------------------- | --------------------------------- |
| October 1 cohort | Enrolled on October 1 (the prototype's test, unchanged)                         | true                              |
| Late joiner      | Not enrolled on October 1, but enrolled on a day from October 2 through June 30 | false                             |

**Terminal grade.** A grade is terminal when the region does not offer the next
grade in the following year (`int_students__school_directory`). Terminal-ness is
a property of the region, not the school: a K-4 school's grade 4 is not terminal
in a K-12 region. For the open cohort, the model uses the current year's grade
list until the next year's list exists. That provisional answer only affects
students who have finished the year, and their outcome is not final until
October 1 anyway.

**Outcome.**

| `persistence_status`     | Finished cohort (on or after the next October 1)                  | Open cohort (before the next October 1)                                                                                                                                  |
| ------------------------ | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Persisted                | Enrolled at any KTAF school on the next October 1                 | Not used                                                                                                                                                                 |
| Completed terminal grade | In a terminal grade, and exited on or after the school's last day | Same, once the last day has passed                                                                                                                                       |
| Left                     | Everyone else                                                     | Withdrew before the school's last day and is not enrolled at any KTAF school today; or withdrew from next year's enrollment; or has a Finalsite summer withdrawal status |
| Active                   | Not used                                                          | Everyone else, including students who finished the year and have shown no sign of leaving                                                                                |

- `is_attrition` is true only for "Left."
- `is_outcome_final` turns true for the whole cohort on the next October 1.
- `has_nonreturn_notice` marks families who told us before the year ended that
  they will not return. It sits beside the status and does not change it.
- The school's last day comes from `int_students__calendar_day`. The prototype's
  June 1 fallback stays for a school the calendar does not cover.

Each row stands alone. For example:

| Student A                                        | 2025-26 row                                               | 2026-27 row                                                   |
| ------------------------------------------------ | --------------------------------------------------------- | ------------------------------------------------------------- |
| Enrolled October 1, 2025; withdrew in March 2026 | Left (`is_attrition` = true), final                       | —                                                             |
| Re-enrolled in November 2026                     | Stays Left: Student A was not enrolled on October 1, 2026 | Late joiner, Active; Persisted if enrolled on October 1, 2027 |

Within a year, the last enrollment decides. A student who leaves in December
2026 and returns in March 2027 has one 2026-27 row, and it reads Active.

Known limits, carried from the prototype:

- About 5 students a year move between New Jersey regions under a new student
  number. They count as Left.
- A few students enrolled on October 1 have a last enrollment without the
  October 1 flag (4 in 2025-26). They fall in the late-joiner group. The
  prototype's 2025-26 numbers treat them the same way.

### Exit reasons and timing

Exit fields are filled only on "Left" rows.

**Matching a Finalsite form to a cohort row.** The model matches a Finalsite
contact to a student on region and student number. A Miami student's number is
`'8400'` followed by the Focus ID. The form's date is the latest Finalsite
withdrawal-status timestamp from the status report, or the last-attended date
when no status exists. A form belongs to cohort year Y when its date falls from
October 1 of Y through September 30 of Y + 1. Finalsite keeps only the latest
answers on a contact, so a student who left in 2 different years gets a reason
on 1 row only.

**Reason fields.**

- From the crosswalk: `exit_reason`, `exit_reason_code`, `exit_category`, and
  `is_controllable`.
- Raw from Finalsite: `finalsite_exit_reason`, `finalsite_exit_category`,
  `fl_state_withdraw_code` (Miami's form only), `finalsite_transfer_type`,
  `exit_comments`, `new_school_name`, `new_school_city`, and `new_school_state`.
- `is_exit_reason_unmapped` flags a Finalsite reason that the crosswalk does not
  cover yet.
- `is_exit_reason_follow_up` flags the "I will follow up with the family within
  10 business days" placeholder.

Category comes from the crosswalk, not the form, so every region reports the
same categories. The form's own category stays in `finalsite_exit_category` for
auditing. The crosswalk fixes 2 problems we found in the current data:

- Regions spell categories differently. Newark writes "Culture" and "Family
  Move" where Camden and Miami write "School Culture" and "Family/Move."
  Paterson's form has no category field.
- Staff sometimes pick a category that contradicts the reason, such as a move
  filed under "Other."

The crosswalk keys on region plus Finalsite reason text. Each row carries a
standard reason label, a code (the existing R, N, or U code where one exists,
and a new KTAF code for each new 2026-27 reason), a category, a controllable
flag, and the school years the reason is in use.

**Withdrawal date.** The first rule that applies wins:

1. The SIS exit date, when it falls before the school's last day.
2. The last day present, when the exit is dated at year end but the student
   missed more than 30 school days before it.
3. The school's last day, when the family told us before the year ended: a
   Finalsite decline or not-enrolling status by June 30, or the New Jersey
   end-of-year bulk-transfer comment (`EOY_BulkTransfer`).
4. The exit date of the next year's enrollment.
5. The Finalsite summer-withdrawal or not-enrolling status date.
6. The Finalsite last-attended date, when it falls after the last day and before
   October 1.

`withdrawal_date_source` names the rule that fired.

**`exit_timing`** buckets the withdrawal date:

| Value              | Rule                                             |
| ------------------ | ------------------------------------------------ |
| Mid-year           | Before the school's last day                     |
| End of year        | Rule 3: the family told us before the year ended |
| Summer             | After the last day, before next year's first day |
| Start of next year | From next year's first day through September 30  |
| Unknown            | No rule fired                                    |

The school calendars supply each school's last day and next year's first day, so
no date is typed into the SQL.

The prototype also used a one-time copy of the July 2026 PowerSchool rollover to
split end-of-year leavers. That copy changed the label of 1 student in 2,144, so
the production model does not need it. New Jersey's rollover comments and
next-year records carry the same evidence.

### Output columns

`rpt_tableau__student_persistence` has one row per `academic_year` and
`student_number`.

| Group                            | Columns                                                                                                                                                                                  |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Year and placement               | `academic_year`, `academic_year_display` ("2025-26"), `region`, `schoolid`, `school_name`, `school_abbreviation`, `grade_level`                                                          |
| Student                          | `student_number`, `student_name`, `gender`, `iep_status`, `spedlep`, `ml_status`, `year_in_network`                                                                                      |
| Enrollment                       | `entrydate`, `exitdate` (the last enrollment of the year), `is_enrolled_oct01`, `is_enrolled_oct15`, `is_late_joiner`, `counts_toward_oct01_persistence`                                 |
| Outcome                          | `persistence_status`, `is_attrition`, `is_outcome_final`, `is_terminal_grade`, `has_nonreturn_notice`                                                                                    |
| Exit, "Left" rows only           | `withdrawal_date`, `withdrawal_date_source`, `exit_timing`, `exit_reason_code`, `exit_reason`, `exit_category`, `is_controllable`, `is_exit_reason_unmapped`, `is_exit_reason_follow_up` |
| Finalsite form, "Left" rows only | `finalsite_exit_reason`, `finalsite_exit_category`, `fl_state_withdraw_code`, `finalsite_transfer_type`, `exit_comments`, `new_school_name`, `new_school_city`, `new_school_state`       |

`iep_status` ("Has IEP" or "No IEP") and `ml_status` ("ML" or "Not ML") use the
same labels as `int_extracts__student_enrollments`, so filters match the other
dashboards. `spedlep` keeps the SIS detail (SPED, SPED SPEECH, No IEP).
`year_in_network` is years at KIPP.

How the dashboard uses the model:

- **Main metric:** persistence = 1 − (count of `is_attrition` ÷ rows), filtered
  to `counts_toward_oct01_persistence`. For an open cohort the same calculation
  reads as "persistence to date."
- **Exit category and reason shares:** counted over "Left" rows.
- **Late-joiner rate:** the same calculation, filtered to `is_late_joiner`.
- **Roster export:** the whole table, with each user limited to their region.

## Dashboard mockup

A first
[dashboard mockup](https://claude.ai/artifact/7QnpNGutb3yfQANxqtWxQa?sk=JPpYZlzAhVWAcmoK2xOcbw#play-15dd8cd198dd)
(KTAF sign-in required) shows how Tableau could use this view. It is a mockup
with made-up data, and the team will refine it. Press Play on its first board to
try the controls.

Key elements:

- **Tab 1, Overview.**
  - Filters for school year, region, school, and grade, plus a "View by"
    control: region, school, grade, region and grade, school and grade, network,
    IEP, ML, gender, or years at KIPP.
  - Network and region tiles: the persistence rate, students still with KIPP,
    students who left, and how many left this week and this month.
  - The persistence rate by the "View by" choice, as bars or as a color-stepped
    grade grid.
  - "Why did students leave?": each exit category's share of leavers, with a
    click-through to the reasons inside it, and a chart of where reasons came
    from.
  - Students who left, by week or month since October 1, split by total, region
    (stacked bars), or school (bubble grid).
- **Tab 2, Students.**
  - A late-joiner panel: how many joined after October 1, how many left, and how
    many are still enrolled, by region. Late joiners stay out of the headline
    rate.
  - A student roster that shows leavers by default, with filters for who to show
    (for example, "left this week" or "late joiners only"), exit category, and
    reason source, plus a CSV download.
- **Build notes.** A board that ties every number to a field and lists gaps,
  rules to confirm, and ideas.

Where the mockup and this design differ:

- The mockup shows "SIS code" as a reason source. Under decision 5, reasons come
  from Finalsite or stay blank, so that chart and filter become Finalsite
  against no reason.
- The mockup counts a student at the school they attended on October 1. This
  design counts them at their last school of the year. See open question 5.
- The mockup asks for roster access by school (its gap 2). This design plans
  region-level row security (see _Access and PII_), which is coarser.

This design already covers 3 of the mockup's gaps and ideas: `student_name` (gap
1), `is_attrition` for late joiners (gap 5), and `is_controllable` for its
"controllable vs not" idea. Its gap 3, a "recorded on" date, is in open
question 6.

## Testing and acceptance

Tests built into the models:

- `rpt_tableau__student_persistence`: an enforced contract and a uniqueness test
  on `academic_year` and `student_number`.
- `persistence_status` and `exit_timing`: not null, and only the allowed values.
- `is_attrition` is true exactly when `persistence_status` is "Left."
- Exit fields are blank on every row that is not "Left."
- The crosswalk: one row per region and Finalsite reason text, with no blank
  code or category.
- Coverage: a warning whenever a Finalsite reason appears that the crosswalk
  does not map.

The model ships only when it reproduces what stakeholders already have:

| Check                    | Pass when                                                                                                                                                     |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2025-26 October 1 cohort | The population equals `ldesimon_dev.student_retention_base` (`academic_year = 2025`) student for student, and persisted = 8,491, allowing for late SIS edits. |
| 2025-26 leavers          | Leavers tie to the prototype by region.                                                                                                                       |
| 2025-26 late joiners     | 369, allowing for late SIS edits.                                                                                                                             |
| 2025-26 exit reasons     | The 1,669 Finalsite-sourced reasons match the prototype student for student. Blanks equal the prototype's 96 blanks plus its 380 PowerSchool-sourced reasons. |
| 2025-26 timing           | Buckets match the prototype (570 mid-year, 664 end of year, 459 summer, 452 start of next year), allowing for the dropped PowerSchool code-entry date.        |
| 2026-27                  | Active plus Left equals the October 1 cohort, and Left equals the students who have exited.                                                                   |

## Access and PII

- The model holds student names, student numbers, free-text exit comments, and
  student-level demographics and outcomes. Its YAML tags those columns with
  `config.meta.contains_pii: true` at the repo's default tiers 1 to 3
  (`.claude/rules/ferpa-pii.md`).
- The new workbook needs region-level row security equivalent to the Ops
  Dashboard's user filter, where each staff group sees only its regions.
- `exit_comments` is free text from families and staff. It can name people and
  circumstances.

## Rollout

1. **PR 1, Finalsite package.** Add New Jersey's `withdrawal_reason_notes_txt`
   to the package pivot. The package change must reach production before the
   kipptaf PR can read the new column.
2. **PR 2, kipptaf.**
   - Widen the kipptaf `int_finalsite__contact_custom_attributes` union to 4
     regions. First confirm that its 3 consumers,
     `rpt_focus__student_enrollment`, `rpt_focus__demographics`, and
     `rpt_focus__contacts`, still filter to Miami.
   - Add the crosswalk Google Sheet source and its staging model.
   - Add the 2 intermediate models, the reporting view, and the exposure.
   - Add a model page under `docs/models/` with a `mkdocs.yml` nav entry.
3. **Tableau.** Build the new workbook on `rpt_tableau__student_persistence` and
   check it against the acceptance numbers. Then hide the Ops Dashboard's
   "Attrition Analysis - Reasons" tab with the workbook owner, and stop
   refreshing the `ldesimon_dev` prototype.

## Open questions

### 1. Finalsite overwrites old answers

_Revised October 30, 2026. We read the Finalsite forms list for every Newark and
Miami contact with withdrawal data, 2,085 contacts in all. Camden and Paterson
are not checked yet._

How Finalsite stores a withdrawal:

- The answers live in contact-level custom fields, which hold 1 value each. A
  new form replaces the earlier answers. All 4 regions store every withdrawal
  field this way, and none of them as a track-siloed field.
- The forms list (`/api/external/contacts/{contact_id}/forms`) returns each
  form's ID, name, submit date, and a PDF link. It returns no answers. Teamster
  does not pull it today.
- A contact can list more than 1 withdrawal form, but the list is not a full
  record. 154 contacts (7%) have withdrawal answers and no withdrawal form in
  the list. 81 of them are enrolled again, and 69 have a "not enrolling" status.
  We do not know yet whether staff delete the form when a student re-enrolls, or
  enter answers without a form.
- The status report also keeps only the latest timestamp for each status. The
  2025-26 and 2026-27 files carry the same timestamps for every student in both
  files. So the model's stand-in for the form date moves whenever a status
  changes again.
- Teamster pulls the `contacts` endpoint once a day and replaces the previous
  pull, so the warehouse keeps no history. BigQuery time travel keeps about 7
  days.

What goes wrong today:

- Between October 1 and October 19, 2026, the prototype lost the Finalsite
  reason on 8 leavers. Finalsite cleared none of them:
  - 6 still carry the same answer. The prototype blanks Finalsite fields for any
    student enrolled today, and all 6 re-enrolled in October.
  - 1 re-enrolled and withdrew again, and the new form replaced the earlier
    answer.
  - 1 lost its form date. The student's withdrawal status changed on October 1,
    2026, which moved the stand-in date out of the 2025-26 window.
- After October 19, 4 more leavers got a different reason. Each now lists 1
  withdrawal form, submitted on October 20, and the earlier answers match no
  listed form.
- A 2025-26 leaver who re-enrolls and withdraws again gets a new form, and the
  new answers replace the 2025-26 answers. The model then fills the 2025-26 row
  with the later answer, or leaves it blank when the later date falls outside
  the window.

Is a student's latest form a clean record of their latest withdrawal? Not yet.

- Of the 107 Newark and Miami students who withdrew from October 1 through
  October 30, 2026, none lists more than 1 withdrawal form. 99 list exactly 1.
  Of the 8 with none, 5 changed schools inside KTAF, 2 are enrolled again, and 1
  withdrew with answers but no listed form.
- Across all 2,085 contacts, 6 list more than 1 withdrawal form. Only 1 of them
  withdrew twice, with each form matching an SIS exit. On that contact, the
  answers carry the older form's last-attended date, so the latest form did not
  clearly win.
- 4 of the 6 have 2 or more forms for 1 SIS withdrawal, which means re-entries
  or corrections. 2 of those include the older "Withdraw KIPP" form next to
  "Withdraw from KIPP Form". The last 1 has no SIS enrollment.
- Submit dates trail the withdrawal. Most forms arrive between 1 day before and
  2 weeks after the SIS exit. 40 Newark forms submitted from late August through
  October list a last-attended date of July 1 or 2.

So a warehouse record per withdrawal must match each form to an SIS exit by the
form's last-attended date, not its submit date, and keep 1 form per exit.

The paths can combine:

- **Keep history in the warehouse.** A daily dbt snapshot of each contact's
  withdrawal answers and forms list (form ID and submit date) needs no Finalsite
  change. When a new form ID appears, the answers on the contact most likely
  belong to that form. Each captured form then matches to an SIS exit, and the
  latest form wins for each exit. The snapshot protects answers only from the
  day it ships, plus the 7 days that time travel can seed.
- **Make the withdrawal fields track-siloed in Finalsite.** A track-siloed field
  stores 1 value per school year. The daily pull already returns every year's
  track-siloed values, tagged with the school year: 6,298 Newark contacts carry
  `assigned_school_ss` for 2 years. So Teamster needs only a dbt pivot by year.
  A second withdrawal in the same school year still replaces the first.
- **Pull the forms list.** It gives each form's real submit date, which replaces
  the status-date stand-in. It does not recover old answers, and old forms can
  be missing from the list. Every contact needs its own call, so `updated_since`
  makes each response smaller but does not cut the number of calls. The
  `contacts` endpoint's `since` filter can limit the calls to contacts that
  changed.
- **Stop blanking answers for re-enrolled students.** That prototype rule hid 6
  of the 8 lost reasons. This design fills exit fields on every "Left" row, so
  its Finalsite-sourced reasons will not tie exactly to the prototype's 1,669.

Questions for the Finalsite admin:

1. Does re-enrolling a student delete their withdrawal form?
2. Do staff enter withdrawal answers on a contact without a form?
3. Can the withdrawal fields become track-siloed? What happens to current
   values, and which school year does a summer withdrawal write to?

Recommendation: build the daily snapshot of answers and the forms list now,
because every day without it loses changes. Ask the Finalsite admin the 3
questions, and decide on track-siloed fields after they answer.

### 2. 2025-26 exit reasons

Decision 5 applies "Finalsite or blank" to 2025-26 as well. In the report
stakeholders hold today, 380 of the 2,145 leavers (18%) took their reason from
PowerSchool. Persistence rates do not change, but the exit reason breakdown
does.

| Region   | 2025-26 leavers | Reason from PowerSchool | Blank in the prototype | Blank under "Finalsite or blank" |
| -------- | --------------- | ----------------------- | ---------------------- | -------------------------------- |
| Newark   | 1,247           | 206                     | 12                     | 218                              |
| Camden   | 432             | 79                      | 2                      | 81                               |
| Miami    | 405             | 95                      | 40                     | 135                              |
| Paterson | 61              | 0                       | 42                     | 42                               |
| Network  | 2,145           | 380                     | 96 (4.5%)              | 476 (22%)                        |

We revisit after launch. One option is to freeze the 2025-26 reasons as
published, in a warehouse table built once from the prototype's October 19
roster. That table would also serve open question 1. It drops out on its own
when 2025-26 leaves the window on October 1, 2027.

### 3. Crosswalk ownership

- Who owns the crosswalk sheet and assigns codes to new 2026-27 reasons?
- Should Teamster pull Finalsite's field definitions (`/api/external/fields`)?
  They list every option on the form, including options no one has picked, so
  the team could map a new reason before its first use. Without them, a new
  reason shows as unmapped on its first use, and the coverage warning fires.

### 4. One definition of persistence

Should the topline Student Retention metric and
`rpt_tableau__student_attrition_over_time` later move onto
`int_students__persistence`? Approach A allows that move but does not include
it.

### 5. Which school a student counts at

This design counts each student at their last school of the year, as the
prototype does. The mockup counts them at the school they attended on October 1.
Few students change schools after October 1 (14 in 2025-26), but the rate a
school sees depends on the rule. The view could carry both schools and let the
dashboard choose.

### 6. Smaller items

- "Active" is a working label.
- The "End of year" timing bucket relies on New Jersey's rollover comment
  convention in PowerSchool.
- The "this week" and "this month" counts use the withdrawal date, so a past
  week's count grows when a school enters a withdrawal late. A "recorded on"
  date, for example from Finalsite status timestamps, would keep past weeks
  stable.

## Out of scope

- Changes to the topline Student Retention metric or the weekly attrition model.
- The Ops Dashboard's enrollment rebuild.
- Cohort years before 2025-26. Exit codes and categories differed, and Finalsite
  forms did not exist.
- PowerSchool and Focus exit codes, for any year.

## Evidence

We ran these checks against the warehouse on October 30, 2026. Every figure is
an aggregate.

- **Ops tab against the prototype, 2025-26.** Attrition by region: Newark 1,543
  against 1,245, Camden 525 against 431, Miami 406 against 406, Paterson 61
  against 61 (the tab hides Paterson). The 392-student gap is entirely grade 12.
- **Prototype logic on 2026-27.** All 11,001 cohort students flagged terminal;
  10,927 "retained" and 74 left.
- **Exit reason sources, 2025-26, from the October 19 roster.** Finalsite 1,669,
  PowerSchool 380, none 96, follow-up placeholder 53.
- **Rollover copy.** It decided the end-of-year label for 1 student, a mid-year
  leaver whose label does not apply.
- **Finalsite field storage.** Every withdrawal field sits in
  `custom_attributes` in all 4 regions, and none in `track_attributes`.
