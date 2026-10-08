# Yearly upkeep

The dbt layer rolls over on its own: all three extracts filter on
`var("current_academic_year")`, which moves each July. The doc's _Start-of-year
procedure_ lists the four things that need a person. This file adds the checks
to run after each one.

| Step                            | Owner                           | Check it happened                                                                                                                                   |
| ------------------------------- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cut scores for a new class      | Data team, when NJDOE publishes | `graduation-pathways` → RUNBOOK: new cut scores, Step 6                                                                                             |
| Community service custom fields | Jabari (DeansList)              | `community-service.md` → QA after the upload                                                                                                        |
| Reporting terms `RT` rows       | Data team                       | Every NJ high school has four `RT` rows (Q1-Q4) for the new year in `stg_google_sheets__reporting__terms`, and appears in the early warning extract |
| Portfolio appeals (June)        | Data team, from C3's PDFs       | `graduation-pathways/references/portfolio-appeals.md` → After the import                                                                            |

Hard-coded values that a new year does not change but a policy change would:

- `rpt_tableau__graduation_requirements`: cohort window
  `current_academic_year - 1` to `+ 5`, and the course filter
  `courses_course_name like 'College and Career%'` for the advisory section.
- `rpt_tableau__hs_early_warning_dashboard`: term names `Summer School` and `Y1`
  are excluded by name.
- Every Tableau threshold (credits 25 / 50 / 85 / 120, ADA 90%, GPA 2.0, 50
  service hours) lives in the workbook.
