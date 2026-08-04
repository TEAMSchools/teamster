# Department-scoped row access for the Survey Dashboard

Refs #4721, #4638

## Problem

The Survey Dashboard's support views ask staff to rate the central and regional
teams that support them. Every viewer who passes `Permissions - Support` sees
every department's feedback, because that field scopes by entity, region, and
school — never by the department being rated.

The rated department is not a column. It exists only as a prefix inside
`question_shortname`, and the naming is inconsistent across surveys:

| Survey                                            | Pattern                    | Examples                                       |
| ------------------------------------------------- | -------------------------- | ---------------------------------------------- |
| `KTAF` (271 respondents, 53 questions)            | `{department}_{n}`         | `finance_1`, `data_2`, `talent_acquisition_oe` |
| `SUP1` / `SUP2` (1,864 respondents, 17 questions) | `{scope}_{department}_{n}` | `cmo_hroperations_5`, `regional_data_1`        |

Two questions break even their own scheme: `sre_oe` sits with
`student_recruitment_*`, and `teaching_and_learning_oe` sits with
`teaching_learning_*`. Others belong to no department at all — `open_ended_1`
through `open_ended_3`, `regional_overall_1`, `cmo_overall_2_oe`, `supplies` —
alongside metadata rows such as `respondent_name` and `school_based`.

Departments have also merged over time, so the mapping from question prefix to
current department is not one-to-one. **A string parse cannot express this**,
and a mis-parsed row is one department reading another's feedback.

The Survey Dashboard is the **last** of the 13 workbooks in the Tableau RLS
rollout still awaiting its edit; every other workbook has been worked.

### What the workbook does today

Read from the published workbook, 2026-08-04:

- **`Question + Job Group Filter`** (383 lines, 25 questions x 11 job titles)
  looks like a permission gate and is not one. `job_title` on
  `rpt_tableau__survey_responses` is the **respondent's** title, so this filter
  controls whose answers are counted for each question. It is a respondent
  exclusion filter and stays exactly as it is.
- **`support_open_ended` carries neither the respondent filter nor the
  `COUNTD(employee_number) >= 4` suppression** that the other four support
  sheets carry. The free-text sheet is the least protected surface in the
  workbook.
- **`Permissions - Support` grants unconditionally to
  `KNJ-SG-Tableau All Staff KTAF`**, so all central office staff see every
  department. This is the same shape as the leak documented in
  `docs/guides/tableau-permissions.md`.
- **`Permissions - Support (Preview)`** is a dead four-line field containing an
  individual by-name grant, the pattern the remediation runbook removes
  everywhere.
- The calc still uses pre-#4656 column names: `legal_entity`, `location`,
  `department`, `job_title`.
- `KNJ-SG-Tableau The Syndicate` is still granted.

## Goals

1. A viewer sees a support response only if they are authorized for the
   department it rates.
2. Cross-department leadership keeps the visibility it has today.
3. A question that rates no department, or whose department has no group yet, is
   visible only to the all-access and cross-department branches.
4. The existing respondent exclusion filter and small-cell suppression keep
   working unchanged.

## Non-goals

- Rewriting `Question + Job Group Filter`.
- Pre-aggregating in dbt. Suppression stays a sheet filter; moving it into the
  warehouse would require enumerating every cut and would break the
  parameter-driven `Cut By` the dashboard is built on.
- Ingesting Tableau group membership. Worth doing, tracked separately; its
  absence is why no test can assert the calc's groups exist.

## Design

### Why the mapping cannot live in Tableau alone

`ISMEMBEROF()` accepts a literal string only. A column holding an authorized
group name cannot be passed to it, and a parameter holds one value per view, so
the calc would evaluate once rather than per row. Group names must therefore be
spelled out in the calc. The question-to-department mapping, which is long and
changes with each survey, belongs in data.

That split is the design:

| Mapping                | Home                      | Why                                                        |
| ---------------------- | ------------------------- | ---------------------------------------------------------- |
| Question to department | Google Sheet, through dbt | Long, survey-driven, edited by Ops without a deploy        |
| Group to departments   | Tableau calc              | Short, authorization, a reviewer must read it in one place |

### Data layer

Extend the **existing** `src_google_sheets__google_forms__form_items_extension`
source. It is already keyed on `abbreviation` = `question_shortname` and already
carries `title`, so no new source, staging model, or Dagster asset is needed.

Two new columns:

| Column                  | Type     | Purpose                                                                                                                                      |
| ----------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `rated_department_code` | `string` | Stable snake_case key the Tableau calc matches. Several question prefixes may share one code — this is how merged departments are expressed. |
| `rated_department_name` | `string` | Display label for the workbook.                                                                                                              |

A question that rates no department gets a blank code.

#### The sheet's own mechanics

Three properties of this source govern how the columns get added, and getting
any of them wrong yields a silently wrong column rather than an error:

- **The declared `columns:` map positionally, not by name.** The sheet's header
  row reads `Form ID`, `Item ID`, `Question ID`, `Title`, `Abbreviation`,
  `URL ID`, while `sources-external.yml` declares `form_id` through `url_id`.
  `skip_leading_rows: 1` discards the header, so BigQuery binds column 1 to the
  first declared name and so on. The two new columns must therefore be appended
  at the **end** of both the sheet and the `columns:` list, in the same order.
- **The `sheet_range` is a named range, not a tab.**
  `src_google_forms__form_items_extension` currently spans columns A through F
  of the `Form Items Extension` tab. Appending sheet columns without widening
  the named range to A through H leaves the new columns invisible to BigQuery.
- **`abbreviation` is not unique in the sheet.** It carries 356 rows at
  2026-08-04, 309 distinct abbreviations across 16 forms; 33 abbreviations
  appear on more than one row, up to 4. See _Join grain_ below.

Files changed:

1. `models/google/sheets/sources-external.yml` — two `columns:` entries on the
   existing source.
1. `models/google/sheets/staging/properties/stg_google_sheets__google_forms__form_items_extension.yml`
   — declare both columns. The staging model is `select *` so its SQL is
   untouched, but the directory default enforces a contract and an undeclared
   sheet column fails the build.
1. `models/surveys/intermediate/int_surveys__survey_responses.sql` — join the
   question-to-department mapping and project both columns. This model already
   owns question identity for both the Google Forms and legacy Alchemer
   branches, so one join covers every row.
1. `models/extracts/tableau/rpt_tableau__survey_responses.sql` and its
   properties — pass both columns through.

#### Join grain

The sheet's grain is `(form_id, item_id)`, not `abbreviation` — the same
question shortname recurs across survey forms and across years. Joining
`question_shortname = abbreviation` directly would fan out a response row once
per matching sheet row, up to 4x, and would break the model's own
`(survey_id, survey_response_id, survey_question_id, question_shortname, answer)`
uniqueness test.

The mapping is therefore projected to one row per shortname before the join, as
a `distinct` over the lowered abbreviation plus the two department columns —
grain projection, valid only because the department a shortname rates is a
property of the shortname and not of the form it appeared on.

That premise needs enforcing, because a typo in one of two sheet rows sharing a
shortname would reintroduce the fan-out. A singular test on the staging model
fails when any abbreviation carries more than one distinct
`rated_department_code`. Without it the `distinct` silently duplicates instead
of deduplicating.

`question_shortname` is lowered on both sides. `rpt_tableau__survey_responses`
already publishes `lower(sr.question_shortname)`, and sheet abbreviations are
entered lowercase but are not constrained to be.

**Left join, deliberately.** A question absent from the sheet yields a null
code, which lands in the same restricted bucket as a blank one. A survey that
ships a new question cannot expose it by default.

### Tableau layer

A new field, `RLS - Department Gate`, kept separate from `Permissions - Support`
and placed beside it on the filter shelf. Two filters both set to `TRUE` is an
AND, and separate fields let either be dropped onto a sheet alone to debug a
persona — the same rationale as the five split RLS fields in the permissions
guide.

```text
// all-access
ISMEMBEROF('KNJ-SG-Tableau All Data')
OR ISMEMBEROF('KNJ-SG-Tableau TC')

// cross-department leadership; entity scoping comes from Permissions - Support
OR ISMEMBEROF('KNJ-SG-Tableau All MDSO')
OR ISMEMBEROF('KNJ-SG-Tableau All HOS')

// department-scoped: one branch per group, an IN list per group
OR (ISMEMBEROF('KNJ-SG-Tableau Special Education Directors')
    AND [rated_department_code] IN ('special_education', ...))
OR (ISMEMBEROF('KNJ-SG-Tableau School Support Directors')
    AND [rated_department_code] IN (...))
OR (ISMEMBEROF('KNJ-SG-Tableau All HR')
    AND [rated_department_code] IN ('human_resources', 'cmo_hroperations'))
// one branch per department that has a group
```

**No `ELSE TRUE`.** A row whose code is blank, null, or names a department with
no group matches no branch, so it is reachable only through the all-access and
cross-department heads. The restricted default is reached by falling off the end
rather than by a rule that could be edited away.

The gate applies uniformly, including to `support_open_ended`. Small-cell
suppression cannot protect free text — one comment is one person — so who may
read it is the only control, and cross-department leadership is inside that
audience.

All-access group names appear in both this field and `Permissions - Support`.
That duplication is the price of keeping the two concerns separate; folding them
together would produce a single calc over 150 lines.

### Respondent identity

**No viewer of the support views sees respondent names, including the rated
department.** This is the decision taken 2026-08-04, and it is what lets the
support surveys be described to staff as anonymous. Department scoping decides
which rows a viewer reaches; this decides that a reached row never shows who
wrote it.

Two fields carry identity: the `respondent_name` column and the
`Teammate (copy)` calculated field that aliases it. Both are removed from every
support sheet — including tooltips, which are the easiest place to leave one
behind — and then hidden in the Data pane so neither can be dragged back on.

Nothing in the calc layer implements this, and that is the point: a wrapper such
as `IF <viewer is departmental> THEN [respondent_name] END` would keep the field
present and one drag away from a support sheet. Removal plus hiding has no such
edge.

Hiding is still not a boundary. Tableau has no column-level security, so a
viewer with Download Data or Web Edit on the workbook can reach
`respondent_name` in the extract regardless. **Anonymity therefore depends on
revoking those two capabilities on the workbook** for every group that is not
all-access; no calculation substitutes for that, and the claim of anonymity is
false without it.

The manager-survey and other non-support views of the same extract are out of
scope — they identify respondents by design, and this change does not touch
them.

### Group coverage

Departments with a group referenced in the workbook today:

| Department code          | Group                                                                  |
| ------------------------ | ---------------------------------------------------------------------- |
| `data`                   | `KNJ-SG-Tableau All Data`                                              |
| `human_resources`        | `KNJ-SG-Tableau All HR`                                                |
| `leadership_development` | `Leadership Development`                                               |
| `teaching_learning`      | `TS-DL-Teaching And Learning`                                          |
| `technology`             | `TS-SG-R9 Technology`                                                  |
| `talent_acquisition`     | `KNJ-SG-Tableau All Recruiting` (confirm)                              |
| `teacher_development`    | `KNJ-SG-Tableau All New Teacher Development` (confirm)                 |
| `special_education`      | `KNJ-SG-Tableau Special Education Directors` (directors, not the team) |

No group is referenced for `compliance`, `finance`, `marketing`, `purchasing`,
`real_estate`, `student_recruitment`, or `advocacy`, nor for the SUP-side
`regional_facilities` and `regional_operations`. Those fall to the restricted
default until groups exist.

A blank cell above means "not referenced in this workbook", not "does not
exist". Server groups cannot be enumerated from here.

Group naming is already three-way inconsistent — `KNJ-SG-Tableau *`, `TS-DL-*`,
`TS-SG-*`, and a bare `Leadership Development`. New departmental groups should
pick one convention and the permissions guide should record which.

### Remediation slice

Independent of everything above, shippable first, each item narrowing access or
deleting dead code:

1. Add `Permissions - Support` and the `COUNTD(employee_number) >= 4` filter to
   `support_open_ended`.
1. Scope the unconditional `KNJ-SG-Tableau All Staff KTAF` grant in
   `Permissions - Support` to the four regions, matching the entity gate in the
   permissions guide.
1. Delete `Permissions - Support (Preview)` and its individual by-name grant.
1. Remove `KNJ-SG-Tableau The Syndicate`.
1. Apply the #4656 renames: `legal_entity` to `home_business_unit_name`,
   `location` to `location_clean_name`, `department` to `home_department_name`.

## Testing

Data layer:

- `not_null` on `abbreviation` in the staging model, so a sheet row cannot lose
  its key.
- A singular test asserting one distinct `rated_department_code` per
  `abbreviation`. This is the guard that makes the join's `distinct` a
  projection rather than a dedupe.
- `accepted_values` on `rated_department_code` against the department list, with
  the blank included as a valid value. Blocked on the taxonomy decision in open
  question 1 — the list cannot be written before the codes are agreed.
- Confirm the join adds no rows: `count(*)` on `rpt_tableau__survey_responses`
  before and after must match.

Workbook personas, run with Preview as User:

| Persona                              | Expect                                                                                              |
| ------------------------------------ | --------------------------------------------------------------------------------------------------- |
| Member of a department group         | Their own department's rows across every region their entity gating allows, and no other department |
| `Special Education Directors`        | Their listed departments only, not all                                                              |
| `All MDSO` or `All HOS`              | Every department, entity-scoped as today                                                            |
| `All Data` or `TC`                   | Everything, unchanged                                                                               |
| A viewer in no departmental group    | Nothing on the support sheets                                                                       |
| Any viewer, on a blank-code question | Visible only if they are all-access or cross-department                                             |
| Every persona above                  | No respondent name anywhere on a support sheet, including tooltips                                  |

Both directions matter. Seeing more than expected is a security finding; seeing
less is a broken gate.

## Open questions

1. **The department taxonomy needs cleanup before the sheet can be filled in.**
   Merged departments must resolve to one current code, and the SUP-side scopes
   (`cmo_*`, `regional_*`) need deciding: one code per department, or separate
   codes per scope.
1. **The `IN` list for each group.** `Special Education Directors` and
   `School Support Directors` get their own department plus a few others; which
   others is not yet decided.
1. **Which of the seven uncovered departments get groups**, and under which
   naming convention.

Resolved 2026-08-04: whether the rated department sees its own respondents'
names. It does not — see _Respondent identity_.
