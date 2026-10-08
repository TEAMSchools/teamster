# Comps debugging and comps-model parity

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

Advanced Comps is the only published view on this model, but an earlier workbook
read found an orphan worksheet, `Sheet 52`, bound to the comps datasource and
placed on no dashboard (not re-checked). Before renaming or dropping a column,
check the `.twb` for it too (`tableau-workbook-xml` skill).

---

## Procedure: A comparison reads false, or a comp is missing

Work in this order.

1. **Is the comparison entity present for that region?** `Neighborhood Schools`
   is Miami only. NJ regions have `City` and `State` only.
2. **Is the subgroup spelling canonical?** The single most common cause. Query
   the distinct `comparison_demographic_subgroup` values in
   `rpt_tableau__state_assessments_dashboard_comps` for the region and year, and
   compare against the vocabulary in [comps-sheet.md](comps-sheet.md) Step 4. A
   value outside it finds no Region partner and every comparison reads `false`.
   A whole subgroup, region or year reading `false` on every test code is this
   signature; a single test code reading `false` is more likely step 3.
3. **Does a Region partner row exist at all?** About a third of the non-Region
   rows have no partner (2026-09-29), overwhelmingly subgroups KTAF has no
   students in. **That is the expected state, not a bug**, and it does not
   surface as a wrong number: Advanced Comps lays the entities out as columns,
   so a missing Region is simply an empty cell. It bites only through the
   `region_outperformed` quick filter, which cannot tell a real loss from an
   absent comparison. Read doc _Comparisons with no Region partner read `false`_
   before investigating.

   A whole test code with no partner is different: check `grade_range_band`.
   `int_tableau__state_assessments_demographic_comps` takes each KTAF row's
   `grade_range_band` from the sheet with `any_value` per test code and school
   level, so a sheet row entered with a different band for the same code and
   level splits the two sides. The ALG01 `MS` rows are `3-8`.

   When diagnosing, relax one join column at a time instead of guessing. Nine
   view-expanding subqueries exceed BigQuery's query-planning limit, so pull the
   view once into memory and do it there: about 15,000 aggregate rows
   (2026-09-29), no PII.

4. **Is the year in the sheet at all?** Official comparison data stops at
   `academic_year = 2024`; later years hold only interim rows (as of the last
   build, AY2025 is NJ `State`, `All Students`, no counts). NJ starts at 2018
   with no 2019 or 2020 rows, Miami starts at 2020, and Paterson at 2023. Read
   the live sheet, not the `stg_` table, before concluding a year is absent.
5. **Is it the wrong comps path?** If the number in question is on Overview,
   Landing Page, Demographics, Proficiency YoY or Teacher/Student Roster, it
   came from the `state_comps` CTE — Total / All Students only, pivoted wide —
   not from the comps model. Debug the CTE, not the view.

---
