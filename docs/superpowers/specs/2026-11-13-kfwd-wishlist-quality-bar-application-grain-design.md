# KIPP Forward wishlist quality bar at the application grain: design

Refs [#6404](https://github.com/TEAMSchools/teamster/issues/6404). Depends on
[#6403](https://github.com/TEAMSchools/teamster/issues/6403).

Status: **draft for team review.** The criteria comparison and data gaps are
verified against prod. The design is a proposal. The open questions at the end
need answers from KIPP Forward before this goes to a plan.

## Intent

Counselors and KIPP Forward leads can see whether a student meets the wishlist
quality bar, but not why. They cannot see which schools count toward which
criterion, which criterion is short, or which single school is holding a student
over the line.

The new model scores each criterion of the bar at 1 row per application. A
reader can then filter to a student and see every school, the criteria each
school satisfies, and how far the student is from each threshold.

The same criteria are scored 4 ways:

| Pool      | Early (EA and ED) criteria | Regular criteria   |
| --------- | -------------------------- | ------------------ |
| Wishlist  | wishlist, early            | wishlist, regular  |
| Submitted | submitted, early           | submitted, regular |

## Decisions so far

- **Each student is held to the criteria for their own GPA band** (KIPP Forward
  confirmed). Today's SQL takes the first branch a student passes, so a 4-year
  student with a 3.8 GPA passes on the 2.00–2.49 criteria (6 schools, all in
  NJ). This is a behavior change: some students who pass today will not.
- **The KNJ 2027 exemplar wishlist document is the source of truth for the
  criteria.** The comparison below shows where it differs from the SQL.
- **A school stays on the wishlist after the student applies.** Today every
  wishlist count filters on the current
  `application_submission_status = 'Wishlist'`, so a school drops out of the
  wishlist counts as soon as the student starts or submits it. The new model
  counts a school as wishlisted when `is_wishlist` (the Salesforce starting
  status was `Wishlist`) or the current status is `Wishlist`.

Impact of the last point, for students with 9+ wishlist schools:

| HS class | Counted today | Ever on the wishlist |
| -------- | ------------- | -------------------- |
| 2027     | 220           | 355                  |
| 2026     | 166           | 334                  |
| 2025     | 50            | 399                  |

## Current state

- `int_kippadb__app_rollup` holds 1 row per student: about 40 count columns plus
  `is_wishlist_quality_bar_int`, `is_submitted_quality_bar_4yr_int`, and
  `is_submitted_quality_bar_ea_int`.
- `rpt_tableau__kfwd_dashboard` repeats the wishlist bar `case` in its own SQL.
  It reads pathway and GPA from the contact, while the rollup reads them from
  the roster. The two copies match today but can drift.
- `rpt_gsheets__kippadb_quality_bar_audit` already has 1 row per wishlisted or
  submitted application, with a flag per criterion and the student's totals. It
  cannot show contribution, and it inherits the current-status problem.
- `base_kippadb__application.starting_application_status` falls back to
  `application_status` (an admission decision such as `Accepted`) when the raw
  field is null. Nothing in this design should read that column; read
  `is_wishlist` instead.

## Criteria: exemplar document vs current SQL

"URM" in the document and "ECC" in the SQL both mean the school's adjusted
6-year minority graduation rate (`adjusted_6_year_minority_graduation_rate`).

| Band               | Current SQL                                                                                                                             | Exemplar document (KNJ 2027)                                                                                                           | Change                                                                                               |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| 4-year, 3.75+      | Part of 3.50+: 9 schools, 7 at 68%+, 4 NJ, 2 meet full need, 1 early that meets full need at 85%+, 2 early at 68%+                      | 10 schools, 4 at 78%+, 8 at 68%+, 2 NJ, 3 meet full need, 1 ED that meets full need at 80%+ (or QuestBridge finalist), 2 EA at 78%+    | New band; stricter except NJ (4 to 2); ED and EA scored separately                                   |
| 4-year, 3.50–3.74  | Same as above                                                                                                                           | 10 schools, 7 at 68%+, 4 NJ, 2 meet full need, 1 ED or EA that meets full need at 80%+, plus 2 more early at 68%+                      | Total 9 to 10; early full-need threshold 85% to 80%; early schools 2 to 3                            |
| 4-year, 3.00–3.49  | 9 schools, 7 at 60%+, 6 NJ, 2 strong out-of-state; EA/ED-designated students also need 2 early at 68%+ and 1 early that meets full need | 10 schools, 7 at 60%+, 6 NJ, 2 strong out-of-state; EA/ED-designated students apply early to 3 at 68%+; avoid the not-recommended list | Total 9 to 10; early criterion becomes 3 at 68%+ with no full-need part; not-recommended list is new |
| 4-year, 2.50–2.99  | 6 schools, 6 NJ, 4 at 55%+                                                                                                              | 9 schools, 6 NJ, 5 at 55%+                                                                                                             | Stricter                                                                                             |
| 4-year, 2.00–2.49  | 6 schools, 6 NJ                                                                                                                         | 6 schools, 6 NJ                                                                                                                        | Same                                                                                                 |
| 4-year, under 2.00 | 3 schools, 3 NJ, 1 "2-year or CTE"                                                                                                      | 3 schools, 3 NJ, 1 community college                                                                                                   | CTE programs no longer count                                                                         |
| 2-year             | 3 "2-year or CTE", or 2 of those plus 1 4-year                                                                                          | 3 total: 2 community colleges plus 1 other option (4-year or CTE)                                                                      | 3 community colleges probably no longer pass                                                         |
| CTE                | 3 "2-year or CTE"                                                                                                                       | 3 total: 2 CTE plus 1 other option                                                                                                     | CTE counted apart from community college                                                             |
| Workforce          | Same as CTE                                                                                                                             | 3 total: "2–3 CTE programs and/or community colleges"                                                                                  | Needs an exact threshold                                                                             |
| Military           | No branch; always fails                                                                                                                 | 3 total: 1 military program plus 2 other options                                                                                       | New branch                                                                                           |
| 3.00+ bands        | None                                                                                                                                    | Balance of reach, target, and likely, "when possible"                                                                                  | Soft; score it or only display it                                                                    |
| Any band           | None                                                                                                                                    | MLL, students with disabilities, EOF, HBCU guidance                                                                                    | Display only (proposal)                                                                              |

The early criteria in the 3.00–3.49 band apply only to students whom KIPP
Forward designated for early applications (`is_ed_ea = 'Yes'` on the roster).
That matches today's split.

## Approaches

### How to split early and regular

- **A. Split the existing criteria (proposed).** Each band's early line items
  (the ED and EA criteria) form the early set. Everything else forms the regular
  set, counted over every school in the pool, early schools included. The
  exemplar document already lists the early criteria as separate items, and the
  3.75+ band separates ED from EA, so no new thresholds are needed.
- **B. Same thresholds, separate pools.** Run the full band criteria over early
  schools only, then over regular schools only. Rejected: "10 early schools" is
  not a realistic bar, so KIPP Forward would have to invent new thresholds.
- **C. One bar, split only in the display.** Keep 1 bar and let readers filter
  contributing schools by admission type. Rejected: it cannot answer "is this
  student's early list on track" before early deadlines.

### Where thresholds live

- **Thresholds in a Google Sheet (proposed).** 1 row per band and criterion: set
  (wishlist or submitted), timing (early or regular), the criterion key, and the
  minimum count. KIPP Forward updates the sheet when the exemplar document
  changes each year, with no code change. The repo does not allow seed files, so
  a sheet is the only data-driven option.
- **Thresholds in SQL.** 1 `case` per band in 1 model. Simpler, but every annual
  criteria change becomes a code change and a deploy.

The criterion _definitions_ (what makes a school "NJ" or "meets full need") stay
in SQL as application flags. Only band membership and minimum counts move to the
sheet.

### How to show influence

- **Contribution (proposed, always on).** Each application row lists the
  criteria it counts toward.
- **Pivotal flag (proposed).** An application is pivotal for a criterion when
  the student's count equals the threshold exactly: dropping that school drops
  the student below the bar. This answers "which schools are holding this
  student up" at no extra cost.
- **Gap.** For each student and criterion, the count still needed. This answers
  "what is missing."

## Proposed design

Layer names follow `.claude/rules/dbt-architecture.md`. Model names are
proposals.

1. **Fix early admission types first** (#6403). `is_early_action` and
   `is_early_decision` must include restrictive early action, early action II,
   and early decision II.
2. **Application flags**: `int_kippadb__application_quality_bar` (build, 1 row
   per application). Reads `base_kippadb__application` and the roster. Adds the
   student's band and 1 boolean per criterion: in the wishlist pool, in the
   submitted pool, early decision, early action, NJ, URM at 55/60/68/78/80/85
   percent, meets full need, strong out-of-state, community college, CTE,
   military, 4-year, reach/target/likely bucket, on the not-recommended list.
3. **Criteria thresholds**: `stg_google_sheets__kippadb__quality_bar_criteria`
   (1 row per band, set, timing, and criterion).
4. **Application × criterion**: `int_kippadb__application_quality_bar_unpivot`
   (reshape). 1 row per application, set, and criterion that applies to the
   student's band, with `is_counted` (the application meets the criterion and is
   in the set's pool), the student's count, the threshold, `is_criterion_met`,
   and `is_pivotal`.
5. **Student result**: 1 row per student, set, and timing with `is_met` and the
   number of criteria short. This replaces the 3 `*_quality_bar_int` columns in
   `int_kippadb__app_rollup` and the duplicated `case` in
   `rpt_tableau__kfwd_dashboard`, so the bar has 1 definition.
6. **Tableau extract**: an `rpt_tableau__` view at application × criterion grain
   for the KIPP Forward dashboard, and the audit sheet rebuilt on step 4.

Students with no band (no pathway, or no GPA on a 4-year pathway) get a band of
`not assessed`, not a failing result.

## Data gaps

1. **QuestBridge or Posse finalist.** No field found in KIPP Forward Salesforce
   staging. Needs a source, or the 3.75+ ED criterion ignores it.
2. **Not-recommended list.** No source. Needs a Google Sheet of accounts.
3. **Community college vs CTE.** Today's SQL lumps 5 account types together.
   `base_kippadb__application` has `is_2yr_college` (`Public 2 yr`) and `is_cte`
   (`type_for_roll_ups = 'Alternative Program'`), but KIPP Forward must confirm
   the definitions, including where programs such as Gateway U land.
4. **Military.** Available: `account_type = 'Military'`.
5. **Balance.** `match_type` exists (Far Reach, Reach, Target, Likely Plus,
   Likely), but the document gives no number.
6. **Which graduation rate.** Our rate comes from the Salesforce account. A
   comment on the exemplar document notes that Overgrad's rates run 10+ points
   lower. Thresholds such as 78% only work if counselors and the model read the
   same number.
7. **Pathway coverage.** 464 of 830 Class of 2027 students in Newark and Camden
   have no `best_guess_pathway`, so they cannot be banded.

## Open questions for KIPP Forward

1. Does the submitted bar use the same criteria as the wishlist bar, or
   different targets?
2. Do withdrawn applications still count toward the wishlist bar?
3. Is approach A (split the existing criteria into early and regular) right?
4. In the 3.75+ band, can the ED school also count toward the 2 EA schools at
   78%+? In the 3.50–3.74 band, does "2 additional early apps" mean 3 early
   schools in total?
5. In the 2-year, CTE, and Military pathways, must the "additional option" be a
   different kind of school (so 3 community colleges fail the 2-year criteria)?
6. What counts as a community college and what counts as CTE?
7. What is the Workforce threshold: 2 or 3 CTE programs or community colleges?
8. Should "balance of reach, target, and likely" be scored? If so, what number?
9. Should the not-recommended list be scored (no listed school on the wishlist)
   or only flagged?
10. Where does QuestBridge or Posse finalist status live?
11. Which graduation rate should thresholds use: Salesforce or Overgrad?
12. How should the dashboard show students with no pathway?

## Left to the builder

- Exact column names, as long as they follow `.claude/rules/dbt-sql.md` and the
  `is_` boolean convention.
- Materialization and tests, per `.claude/rules/dbt-models.md` (uniqueness on
  every new model; `error` tests on the `rpt_` model).
- Whether the audit sheet is rebuilt on the new model or retired.
