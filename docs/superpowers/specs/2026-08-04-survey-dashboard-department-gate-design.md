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
- Anonymizing the rated department's own view. See _Respondent identity_ below
  for what is in scope.
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

Files changed:

1. `models/google/sheets/sources-external.yml` — two `columns:` entries on the
   existing source.
2. `models/google/sheets/staging/properties/stg_google_sheets__google_forms__form_items_extension.yml`
   — declare both columns. The staging model is `select *` so its SQL is
   untouched, but the directory default enforces a contract and an undeclared
   sheet column fails the build.
3. `models/surveys/intermediate/int_surveys__survey_responses.sql` — left join
   the staging model on `question_shortname = abbreviation` and project both
   columns. This model already owns question identity for both the Google Forms
   and legacy Alchemer branches, so one join covers every row.
4. `models/extracts/tableau/rpt_tableau__survey_responses.sql` and its
   properties — pass both columns through.

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

Department scoping and anonymity are separate rules and neither implies the
other. A cross-department viewer sees a row **without** the respondent's name;
the department gate decides which rows they reach, this decides what a reached
row shows.

Two fields carry identity: the `respondent_name` column and the
`Teammate (copy)` calculated field that aliases it. Both are wrapped:

```text
IF [RLS - Department Gate Is Departmental] THEN [respondent_name] END
```

where `RLS - Department Gate Is Departmental` is true when the viewer reaches
the row through a department branch rather than a cross-department one. The raw
`respondent_name` and `Teammate (copy)` are then hidden in the Data pane so
neither can be dragged onto a sheet ungated.

This is a display gate, not a boundary. Tableau has no column-level security, so
a viewer with Download Data or Web Edit on the workbook can still reach
`respondent_name` in the extract. If the name must be genuinely unreachable,
those two capabilities have to be revoked on the workbook; no calculation
substitutes for that.

Note the scope limit: this hides the name from cross-department viewers only.
Whether the rated department sees the names of its own respondents is open
question 4.

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
2. Scope the unconditional `KNJ-SG-Tableau All Staff KTAF` grant in
   `Permissions - Support` to the four regions, matching the entity gate in the
   permissions guide.
3. Delete `Permissions - Support (Preview)` and its individual by-name grant.
4. Remove `KNJ-SG-Tableau The Syndicate`.
5. Apply the #4656 renames: `legal_entity` to `home_business_unit_name`,
   `location` to `location_clean_name`, `department` to `home_department_name`.

## Testing

Data layer:

- `not_null` on `abbreviation` in the staging model, so a sheet row cannot lose
  its key.
- `accepted_values` on `rated_department_code` against the department list, with
  the blank included as a valid value.
- Confirm the join adds no rows: `count(*)` on `rpt_tableau__survey_responses`
  before and after must match, since a duplicated `abbreviation` in the sheet
  would fan out.

Workbook personas, run with Preview as User:

| Persona                              | Expect                                                                                              |
| ------------------------------------ | --------------------------------------------------------------------------------------------------- |
| Member of a department group         | Their own department's rows across every region their entity gating allows, and no other department |
| `Special Education Directors`        | Their listed departments only, not all                                                              |
| `All MDSO` or `All HOS`              | Every department, entity-scoped as today                                                            |
| `All Data` or `TC`                   | Everything, unchanged                                                                               |
| A viewer in no departmental group    | Nothing on the support sheets                                                                       |
| Any viewer, on a blank-code question | Visible only if they are all-access or cross-department                                             |

Both directions matter. Seeing more than expected is a security finding; seeing
less is a broken gate.

## Open questions

1. **The department taxonomy needs cleanup before the sheet can be filled in.**
   Merged departments must resolve to one current code, and the SUP-side scopes
   (`cmo_*`, `regional_*`) need deciding: one code per department, or separate
   codes per scope.
2. **The `IN` list for each group.** `Special Education Directors` and
   `School Support Directors` get their own department plus a few others; which
   others is not yet decided.
3. **Which of the seven uncovered departments get groups**, and under which
   naming convention.
4. **Does the rated department see its own respondents' names?** The design
   hides names from cross-department viewers only. Hiding them from the
   department as well is a one-word change to the wrapper, but it is a policy
   call, not a technical one — and it affects whether the survey can be
   described to staff as anonymous.
