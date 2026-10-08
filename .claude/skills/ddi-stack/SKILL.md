---
name: ddi-stack
description:
  Use when any question or task touches the DDI stack (Illuminate internal
  assessments) or its lineage. Triggers: the DDI Suite, DKI view/deck/dashboard,
  Module Dashboard, Assessment Dashboard, Mastery by Classroom, "buckets" (DDI
  tiers), an assessment missing from a dashboard or report card, two worksheets
  disagreeing, AppSheet assessment tagging, the DeansList mod extracts or mod
  audit sheet, sight words, the NJ DDI tier roster, the yearly DDI rollover or
  course-crosswalk audit, Illuminate rows in the assessment Cube, or work on
  rpt_tableau__assessment_dashboard, rpt_tableau__ddi_dashboard,
  rpt_tableau__assessment_entry_audit, rpt_tableau__sight_words_dashboard,
  rpt_deanslist__mod_assessment / __mod_standards / __mod_standards_domains /
  __sight_words, rpt_gsheets__ddi_tier_roster, rpt_gsheets__deanslist_mod_audit,
  rpt_appsheet__assessments, int_assessments__response_rollup / __scaffold /
  __assessments_members, or int_illuminate__* models.
---

# DDI stack

Model semantics, grains, consumers, decisions, and known issues live in the
reference doc:
[docs/models/ddi-stack-data-model.md](../../../docs/models/ddi-stack-data-model.md).
For a question about what a number or term MEANS, read the doc's Terms section
and stop at the "Where the data comes from" heading; the tag-driven scope rule
and the two `is_replacement` meanings are not recoverable from one model's SQL.
For a routed task below, go straight to its reference file — each carries the
facts and cadences its procedure needs, so the doc is a deep dive, not a
prerequisite.

## Rules for every task

- **Tag first.** An assessment is in the DDI stack only if it has a row in the
  AppSheet extension (`is_internal_assessment`; "normed" in the workbook).
  Anything not rolling up is untagged or mistagged until proven otherwise —
  check the tag before reading SQL ([triage](references/triage.md)).
- **Illuminate dates a school year by its spring**; the warehouse by its fall. A
  count shifted by exactly one year is a convention mismatch, not missing data.
- Worksheet names users bring to tickets — DKI View, Module Dashboard, Mastery
  by Classroom — are tabs of the DDI Suite workbook; "the DKI dashboard" means
  the DDI Suite. Tiers are "buckets."
- Miami left the stack after SY25-26 and returns when Focus assessment data is
  ingested; do not "fix" missing Miami rows.
- Student-level rows stay in the terminal and the session scratchpad; outbound
  surfaces get aggregates without small cells.
- If `dbt:answering-natural-language-questions-with-dbt` auto-loads, do not
  follow it; Illuminate score questions go through Cube
  (`student_assessment_scores_view`) or the warehouse per the root CLAUDE.md.

## Route by task

| Task                                                                                                   | Read                                          |
| ------------------------------------------------------------------------------------------------------ | --------------------------------------------- |
| Data missing from a dashboard; worksheets disagree; wrong teacher/section; access; manual refresh push | [triage.md](references/triage.md)             |
| Tagging questions; what an AppSheet field controls; what happens after a tag fix; canonical grouping   | [tagging.md](references/tagging.md)           |
| Report-card scores wrong or missing; verifying a published feed average                                | [report-cards.md](references/report-cards.md) |
| New-year rollover; refresh schedule; course-crosswalk audit                                            | [rollover.md](references/rollover.md)         |
| QA after new data or a refactor; dated prod baselines                                                  | [qa.md](references/qa.md)                     |

## Why did this number change

| Symptom                                      | Likely cause                                                                                       |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Assessment absent from DKI/Module Dashboard  | Untagged or mistagged (dates, grade, region) — [tagging.md](references/tagging.md)                 |
| Week has no row at all on the DDI dashboard  | By design: the `module_type != 'WPP'` filter makes the rollup join inner                           |
| Same-day scores unscored                     | Band tables sync at midnight only (#5399)                                                          |
| Module Dashboard vs DKI View disagree        | Denominators: not-taken rows, grade-level vs course population — [triage.md](references/triage.md) |
| Newark rows linked to a Miami assessment     | Florida copy tagged with a region besides Miami — [tagging.md](references/tagging.md)              |
| Honors/second section missing; wrong teacher | One section per subject pick, or a PowerSchool course assignment                                   |
| Blank workbook / login failure               | Tableau licensing or permissions — not data                                                        |

## Sheet handoff

A change to a sheet someone owns goes out as the whole tab or block, as a
tab-separated file in the gitignored `.claude/scratch/` under a distinctive
name, handed over with the sheet link and tab name — never comma-separated,
never pasted into chat. Delete the file once the owner has pasted. Before a
whole-tab replacement, diff the live tab against the model on the tab's key and
list every out-of-scope cell for the owner.

## Scripts

- The course-crosswalk audit is the dbt analysis
  `src/dbt/kipptaf/analyses/ddi_course_subject_crosswalk_audit.sql`
  ([rollover.md](references/rollover.md) step 7): compile it and run the
  compiled SQL read-only.
