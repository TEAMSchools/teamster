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

The mapping gets its **own** sheet:
`src_google_sheets__google_forms__question_department_crosswalk`, a new
`Question Department Crosswalk` tab on the same spreadsheet that already backs
`src_google_sheets__google_forms__form_items_extension`.

An earlier version of this design extended the `form_items_extension` source
instead, on the reasoning that it already carries `abbreviation` and `title` so
no new source, staging model, or Dagster asset would be needed. That was the
wrong trade. The department a question rates is a property of the abbreviation
alone, while that sheet's grain is `(form_id, item_id)` — 356 rows carrying 309
distinct abbreviations, with 33 abbreviations recurring across up to 4 rows.
Storing the mapping there forced Ops to enter the same value up to four times,
made contradictory entries representable, and needed a `distinct` projection
plus a bespoke guard test to hold the join together. A sheet keyed on
`abbreviation` needs none of that. The cost is a source block, a two-line
staging model, and a properties file; sheet sources need no Dagster Python
change, and 26 of the 88 sheet sources in `sources-external.yml` are already
standalone crosswalks or lookups.

Three columns:

| Column                  | Type     | Purpose                                                                                                                                  |
| ----------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `abbreviation`          | `string` | Question shortname, lowercase. The join key.                                                                                             |
| `rated_department_code` | `string` | Stable snake_case key the Tableau calc matches. Several abbreviations may share one code — this is how merged departments are expressed. |
| `rated_department_name` | `string` | Display label for the workbook.                                                                                                          |

A question that rates no department gets a blank code, which stages as `NULL`.

#### The sheet's own mechanics

Two properties of sheet sources govern how the crosswalk gets built, and getting
either wrong yields a silently wrong column rather than an error:

- **The declared `columns:` map positionally, not by name.**
  `skip_leading_rows: 1` discards the header row, so BigQuery binds column 1 to
  the first declared name and so on. A column inserted into the middle of the
  tab misaligns everything to its right, `abbreviation` included. Reference
  columns for the humans filling the sheet are fine, but they belong past the
  last mapped column.
- **The `sheet_range` is a named range, not a tab.** The crosswalk's range is
  `src_google_forms__question_department_crosswalk` over
  `'Question Department Crosswalk'!A:C`. Columns outside the range are invisible
  to BigQuery, which is what makes the reference columns safe — and what makes a
  range that disagrees with the `columns:` list a silent error.

The same two properties governed the original approach, plus a third: appending
to a shared sheet meant widening an existing named range from `A:F` to `A:H`
without disturbing the six columns already bound. Reverting it needed only the
column delete — both external tables declared 6 columns throughout, so neither
ever saw `G` or `H`.

#### Join grain

The crosswalk is one row per abbreviation, which is the grain
`int_surveys__survey_responses` joins on, so the join is a plain left join with
no projection:

```sql
left join
    question_departments as qd on lower(e.question_shortname) = qd.question_shortname
```

`question_shortname` is lowered on both sides. `rpt_tableau__survey_responses`
already publishes `lower(sr.question_shortname)`, and sheet abbreviations are
entered lowercase but are not constrained to be.

That lowering is the one thing that can still break the grain. A column-level
`unique` on `abbreviation` does not protect it: two rows entered as `A1` and
`a1` both satisfy `unique` and then collide once lowered, fanning out every
response for that question. Uniqueness is therefore asserted on the **lowered**
value, by the `unique_lowered_abbreviation` singular test, which subsumes the
raw `unique` test rather than sitting alongside it.

### Tableau layer

A new field, `RLS - Department Gate`, referenced from **inside**
`Permissions - Support` as its own tier — not placed beside it on the filter
shelf.

Two filters both set to `TRUE` is an AND, which applies the department gate to
every viewer including the all-access and cross-department-leadership tiers.
Those viewers belong to no department group, so an AND-ed gate drops them to
zero rows. The gate has to be a disjunct inside the existing calc, so that
department-scoped access is _added_ for department members rather than
_subtracted_ from everyone else:

```text
//Tier 4b — department-scoped: own department's questions, own region
OR ([RLS - Entity Gate] AND [RLS - Department Gate])
```

Department groups move out of the all-access and region-scoped tiers into this
one. A group left in the all-access tier keeps seeing every department's
feedback, which is the condition this design exists to end.

`RLS - Department Gate` itself is a `CASE` over the code, one branch per
department, rather than one branch per group with an `IN` list. The codes are
the stable side of the mapping and the sheet guarantees one code per
abbreviation, so keying on the code reads directly against the pinned
`accepted_values` list:

```text
IFNULL(
  CASE [rated_department_code]
    WHEN 'data'                        THEN ISMEMBEROF('KNJ-SG-Tableau All Data')
    WHEN 'human_resources_operations'  THEN ISMEMBEROF('KNJ-SG-Tableau All HR')
    WHEN 'special_education'           THEN ISMEMBEROF('KNJ-SG-Tableau Special Education Directors')
    WHEN 'technology'                  THEN ISMEMBEROF('TS-SG-R9 Technology')
    //one branch per code in the pinned 14
  END,
  FALSE
)
```

Three mechanics that are easy to get wrong:

- **`ISMEMBEROF()` returns NULL when the viewer is not signed in**, not `FALSE`.
  Hence the `IFNULL(..., FALSE)` wrapper, and never `NOT ISMEMBEROF(...)` — a
  negated NULL stops behaving like a gate.
- **Group names containing non-alphanumeric characters need HTML URL encoding**
  inside `ISMEMBEROF()`. `KNJ-SG-Tableau All T&L` must be written
  `KNJ-SG-Tableau All T%26L`; written literally the branch silently never
  matches.
- **Every failure mode is fail-closed.** A misspelled group, a group not yet
  created, a viewer not signed in, or a new code absent from the `CASE` all
  yield no rows rather than extra rows.

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

Verified against `stg_ldap__group` across all four naming schemes
(`KNJ-SG-Tableau`, `TS-SG-`, `TS-DL-`, `Group Staff`), with member counts
compared to ADP `home_department_name` headcount.

Ten of the fourteen codes already have a usable group:

| Department code              | Group                                        | Members | ADP |
| ---------------------------- | -------------------------------------------- | ------- | --- |
| `data`                       | `KNJ-SG-Tableau All Data`                    | 10      | 10  |
| `human_resources_operations` | `KNJ-SG-Tableau All HR`                      | 14      | 14  |
| `teacher_development`        | `KNJ-SG-Tableau All New Teacher Development` | 7       | 7   |
| `talent_acquisition`         | `KNJ-SG-Tableau All Recruiting`              | 16      | 15  |
| `special_education`          | `KNJ-SG-Tableau Special Education Directors` | 9       | 325 |
| `teaching_learning`          | `TS-DL-Teaching And Learning`                | n/a     | 25  |
| `technology`                 | `TS-SG-R9 Technology`                        | 22      | 34  |
| `finance`                    | `TS-SG-R9 Finance` + `TS-SG-R9 Purchasing`   | 13 + 3  | 15  |
| `development`                | `TS-SG-R9 Development`                       | 3       | 5   |
| `real_estate_facilities`     | `TS-SG-R9 Facilities`                        | 2       | 3   |

`special_education` is deliberately the directors group rather than the
325-person department. `TS-SG-R9 Technology`, `Development`, and `Facilities`
are each short of their ADP headcount and need a membership reconciliation
before they are relied on — an under-populated group means real staff silently
see nothing.

Four codes have no group and need one created: `compliance`,
`leadership_development`, `marketing_comms_enrollment`, and `operations`.
Proposed convention for new groups is `KNJ-SG-Tableau Dept {Department}`, the
`Dept` infix separating them from the location and role groups. `operations` may
instead reuse `KNJ-SG-Tableau All DSO` + `All MDSO` rather than create a
172-person group.

Two caveats on this inventory. `stg_ldap__group` is on-prem AD, so an
Entra-native group would not appear in it — absence is not proof. And
`TS-DL-Teaching And Learning`, referenced by the workbook today, was not found
under that exact CN; the near matches are `TS-DL-TeachingAndLearning` (27) and
`Group Staff Teaching and Learning` (27). Confirm against the Tableau site's own
group list, which cannot be enumerated from here.

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

- **No `not_null` on `abbreviation`.** An earlier draft of this spec called for
  one; it would fail the moment the sheet grows blank rows. The named range is
  row-unbounded, so BigQuery can surface fully-blank phantom rows below the data
  — that is what makes the sibling `form_items_extension` sheet stage roughly
  525 null abbreviations out of 881 rows, since its section-header rows also
  carry a `Title` and no abbreviation. The crosswalk stages clean today at 309
  rows with no nulls, but every consumer filters
  `where abbreviation is not null` rather than depending on that.
- `unique_lowered_abbreviation`, a singular test at `severity: error`, asserting
  one row per lowered `abbreviation`. This is what protects the join's grain —
  see _Join grain_ for why the generic `unique` test does not.
- `covers_all_abbreviations`, a singular test at `severity: warn`, asserting
  every non-null `abbreviation` in `form_items_extension` has a crosswalk row.
  This is the one failure mode a separate sheet introduces: a question on a new
  survey form arrives with no mapping. It fails safe — a null department routes
  to the most restricted audience — so it warns rather than blocking a build.
  Passing at 309 of 309.
- `accepted_values` on `rated_department_code` against the agreed 14 codes.
  Shipped and passing, with all 14 in use. The blank case needs **no** entry in
  the list — `accepted_values` compiles to `where value not in (...)`, which
  `NULL` never satisfies, so nulls pass regardless. Blank sheet cells do stage
  as `NULL` rather than empty string, confirmed against the staged table. Adding
  an empty-string entry would only mask a genuinely empty-string value.
- Confirm the join adds no rows. The decisive check is the model's own
  `dbt_utils_unique_combination_of_columns` on
  `(survey_id, survey_response_id, survey_question_id, question_shortname, answer)`
  — that is the test a fan-out breaks. A `count(*)` comparison against prod
  corroborates it but cannot stand alone, because `zz_stg` and prod drift by
  whatever responses arrived since the last clone.

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

1. **Which groups stay all-access.** `KNJ-SG-Tableau All Staff KTAF` (171
   members) sees every department's feedback while it remains in the all-access
   tier, which would leave this work with no practical effect. `All Data` may
   legitimately need everything to build and debug the dashboard.
   `KNJ-SG-Tableau AcOps` (1 member) needs a tier.
1. **Membership reconciliation** for `TS-SG-R9 Technology` (22 of 34),
   `TS-SG-R9 Development` (3 of 5), and `TS-SG-R9 Facilities` (2 of 3), plus
   confirmation of the real `TS-DL-Teaching And Learning` CN.
1. **Whether `operations` gets its own 172-person group** or reuses `All DSO` +
   `All MDSO`.

Resolved 2026-08-04: whether the rated department sees its own respondents'
names. It does not — see _Respondent identity_.

Resolved 2026-08-05: the department taxonomy. One code per function, with
`regional_*` and `cmo_*` question families folded into the unprefixed function —
fourteen codes, pinned by `accepted_values`. `purchasing_*` carries `finance`,
`student_recruitment_*` and `sre_oe` carry `marketing_comms_enrollment`,
`real_estate_*` and `regional_facilities_*` both carry `real_estate_facilities`,
and the retired `advocacy_*` questions carry `development`. The full list is in
the plan's _Department taxonomy, as shipped_ section.
