# Tableau Permissions

How row-level security works on our Tableau workbooks — who can see whose data,
and how it is implemented.

This page has two halves. **Part 1** is for anyone who wants to understand or
question what they can see, and needs no Tableau knowledge. **Part 2** describes
the field structure and points at the build reference.

**Status: live, with six known gaps.** Eleven workbooks were remediated during
the Entra ID identity migration and carry the model described here. An audit on
2026-08-05 read the shipped calculations for the first time and found six places
where a workbook does not match this description — see _Known gaps_ in Part 2
before relying on a specific workbook.

---

## Part 1 — Who can see what

### The short version

Access is decided **per row**, not per dashboard. Opening a workbook does not
show you everything in it; it shows you the rows you are entitled to. Two people
looking at the same dashboard routinely see different numbers, and that is
working as intended.

Entitlement comes from **which Tableau groups you belong to**, not from your job
title or your position in the org chart. This is deliberate — it means access
can be granted or removed by changing a group, with no change to any workbook.

### The five ways you can be shown a row

You see a row if **any one** of these is true. They are additive.

|     | Route                    | You see                                                                                        |
| --- | ------------------------ | ---------------------------------------------------------------------------------------------- |
| 1   | **You, or your manager** | Your own row. Your direct reports' rows.                                                       |
| 2   | **A network-wide group** | Everything, for a small number of functional groups such as the data team and HR.              |
| 3   | **Regional operations**  | Your region's rows, if you are in a regional ops group.                                        |
| 4   | **Regional leadership**  | Your region's rows, if you are a regional leader.                                              |
| 5   | **Your school**          | Your school's rows, if you are in that school's staff group _and_ hold a role that permits it. |

Route 5 needs all three of the right entity, the right school, and a qualifying
role. Missing any one of them means no access by that route.

!!! note "Route 3 does not currently reach Paterson"

    The regional operations route names TEAM and KIPP Cooper Norcross for NJ, and
    Miami for Miami. Paterson appears in the entity and school routes but not in
    route 3, so NJ regional ops staff do not reach Paterson rows by that route.
    Whether Paterson joins the NJ group or gets its own is an open decision.

### What central office can and cannot see

Central office (KTAF) staff have **oversight of the regions, not of each
other**.

Being in the central office group grants visibility into TEAM, KIPP Cooper
Norcross, KIPP Miami, and KIPP Paterson rows. It does **not** grant visibility
into other central office rows. Those are reachable only by being the person
themselves, being their direct manager, or belonging to one of the network-wide
groups in route 2.

!!! note "A known consequence"

    A central office director does not see their reports' reports. Route 1 covers
    only the _direct_ manager. This is accepted rather than accidental — the
    reasoning is in the design spec linked at the end of this page.

### Senior leaders are shielded further

On the workbooks that carry performance and development data, rows belonging to
senior leaders are restricted to that person, their manager, and the
network-wide groups. Peers at the same level do not see each other, including
peers who otherwise have broad access.

Seniority is read from the ADP job function rather than from job title text, so
a newly created senior title is covered automatically without anyone editing a
workbook. Where the job function is missing, a job-title fallback applies —
which currently over-reaches by one role, shielding executive assistants as
though they were executives.

### The Intent to Return survey is different

Intent to Return answers reach fewer people than anything else on Tableau, and
who they reach depends on your own level. **Nobody at your own level ever sees
them.**

| If you are                                       | Your answers reach                                                                                                                                                                        |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A teacher or learning specialist                 | Your manager, your school's assistant principals, your school leader and director of school operations, your regional leadership, and the HR, Recruiting and Leadership Development teams |
| An assistant school leader                       | Your manager, your school leader and director of school operations, your regional leadership, and those three teams — **not** other assistant principals                                  |
| A school leader or director of school operations | Your manager, your regional leadership, and those three teams — **not** other school leaders or DSOs                                                                                      |
| A departmental director                          | Your manager, your region's senior leadership, and those three teams — **not** other directors in your department                                                                         |
| Regional leadership                              | Your manager and those three teams — **not** other regional leaders                                                                                                                       |
| Central office staff                             | Your manager and those three teams. No regional leader sees central office answers                                                                                                        |

The TEAM Council sees every response network-wide except other chief-level
respondents.

Roles in training are treated as the level they are developing into, not the
level above: a school leader in residence, a school operations fellow and an
associate director of school operations are all visible to their school's
leadership, the same as an assistant school leader is.

Two further protections apply to everyone. A manager who changes roles does not
keep access to your older answers, and a new manager does not gain access to
answers you gave before they managed you. And the free-text boxes carry the same
restriction as the rest — there is no wider audience for comments.

!!! warning "Peer exclusions match the title you held when you answered"

    Every attribute on a survey response is a snapshot from the moment it was
    given, while Tableau group membership is always current. So a school leader
    sees three years of their school's answers, including their predecessor's
    staff — and someone who changes schools leaves their old answers with the old
    school's leadership.

### Rooms do not grant access

Working in a Room — the office locations rather than a school — does not grant
visibility of that Room's occupants. Room-based staff reach data through the
network-wide and regional-leadership routes instead.

This matters because Rooms are shared: Room 9 has occupants from more than one
entity, so treating a Room like a school would hand people access across entity
lines.

### Why you might see less than a colleague

In rough order of likelihood:

1. They are in a group you are not in. Group membership is the whole mechanism.
1. They are the person's manager and you are not.
1. The row belongs to a senior leader, and neither of you should see it — but
   they are in a network-wide group.
1. The row belongs to central office, and central office rows are not visible to
   other central office staff.

### How to get access

**Ask to be added to the relevant Tableau group.** Do not ask for a workbook
change. Every route above is driven by group membership, so a group change is
immediate, auditable, applies consistently across all workbooks, and is
reversible. A workbook edit is none of those things.

Individual, by-name grants inside a workbook are **not permitted**. They are
invisible to anyone auditing group membership and they survive the person
changing roles. The Entra ID migration removed them from the main `Permissions`
field of every workbook; the 2026-08-05 audit found 16 still present in
secondary permission fields, which are being removed.

---

## Part 2 — What the fields are

Row-level security is implemented as Tableau calculated fields inside each
workbook. This section describes the structure so you can read a workbook and
know what you are looking at.

**To build or repair a workbook, use the playbook** —
`docs/superpowers/plans/2026-07-31-tableau-workbook-remediation.md`. It carries
the paste-ready text of every field, the order to create them in, the field-name
resolution step, the apply-scope decision, and the per-workbook variants. That
is the only place the calc text lives; this page deliberately does not duplicate
it.

### The five fields

Four are needed in every gated workbook; the fifth only where senior leaders are
shielded from each other.

| Field                            | Answers                                                                           |
| -------------------------------- | --------------------------------------------------------------------------------- |
| `RLS - Entity Gate`              | Is the viewer in the staff group for this row's entity?                           |
| `RLS - Location Gate`            | Is the viewer in the staff group for this row's location?                         |
| `RLS - Role Gate`                | Does the viewer hold a role that may see school-based rows?                       |
| `RLS - Subject Is Senior Leader` | Should this row be shielded from peers?                                           |
| `Permissions`                    | The five routes from Part 1. **This is the field that gets applied as a filter.** |

The split exists because the entity gate is needed by both route 4 and route 5,
because per-workbook variants become one-line edits to a small field rather than
surgery inside a sixty-line calculation, and because each gate can be dropped on
a sheet by itself and compared against a row — which is how you debug a persona
seeing the wrong thing.

Two properties of the design are worth knowing when reading any of these:

- **The gates read group membership, never the viewer's own roster row.** That
  is how cross-entity supervision works: someone employed by TEAM who oversees
  Paterson gets Paterson visibility by being added to the Paterson group, with
  no calculation change. Deriving entity from the viewer's own row would
  silently revoke access from every cross-entity supervisor.
- **`ISMEMBEROF()` takes a literal string only**, so the location gate is 26
  explicit branches rather than one expression built from a field. A parameter
  does not substitute: it holds one value per view, so the calculation would
  evaluate once instead of per row and degenerate to all-rows-or-none.

!!! warning "A missing group does not error — it silently denies"

    Before editing a workbook, confirm every location group exists. The dbt test
    `int_people__staff_roster__tableau_location_set_expected` asserts the data side
    of this invariant; nothing can assert the Tableau side.

### Where a permission field gets applied

Tableau **ANDs** every filter that reaches a mark, so where the field is
attached decides how much it covers:

| Scope                                 | Covers                                                     |
| ------------------------------------- | ---------------------------------------------------------- |
| All worksheets using this data source | every sheet on that datasource, including ones added later |
| Data source filter                    | same                                                       |
| This worksheet only                   | that one sheet                                             |

Datasource-wide is the default and what most workbooks use. Sheet-local scope is
correct only when one datasource genuinely needs two different rules — the
Survey Dashboard's Intent to Return sheets versus its support sheets, for
instance.

Two consequences that have both caused real problems:

- A sheet-local gate has to be re-applied by hand on every new sheet. Add a
  sheet to a dashboard, forget the filter, and it is ungated.
- Where both scopes are attached, effective access is the intersection — so a
  datasource-wide gate silently masks the defects of a stale sheet-local one.
  The containment disappears the moment someone removes the wider filter or
  copies the stale field into a new workbook.

### One workbook can hold several permission fields

A workbook is not finished when `Permissions` is correct. Several carry
additional gates for particular sheets, and **each is a separate copy of the
tier chain** maintained independently. SchoolMint Grow has five; the Survey
Dashboard has two.

Two mechanics make these hard to find, and both are why the audit needed the
`.twbx` files rather than the Tableau UI:

- A filter stores the field's **internal** name, which never updates on rename.
  A filter reading `Permissions - ITR (copy)_155726081272713223` displays as
  `Permissions - Support`.
- A dead permission field passes every persona test, because nothing filters on
  it — and it is the natural thing to copy when someone next adds a sheet.

### The gated workbooks

Eleven workbooks carry a `Permissions` field. All sit in the `Production`
project and all are tagged `entra-ready` on Tableau Server. **That tag is the
inventory** — a gated workbook without it is either unfinished or was built
without following the playbook.

| Workbook                          | Datasource                                                                                                                    |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Manager Survey Reports            | `rpt_tableau__manager_survey_details`                                                                                         |
| Manager Survey Rollup             | `rpt_tableau__manager_survey_details`                                                                                         |
| Leadership Development            | `rpt_tableau__leadership_development`                                                                                         |
| Coaching Conversation Tool        | `rpt_tableau__schoolmint_grow_observation_details`                                                                            |
| SchoolMint Grow Dashboard         | `rpt_tableau__schoolmint_grow_observation_details`, `rpt_tableau__schoolmint_grow_goals`, `rpt_tableau__teacher_observations` |
| Survey Dashboard                  | `rpt_tableau__survey_responses`, `rpt_tableau__survey_completion`                                                             |
| Miami Instructional Rubrics       | `rpt_tableau__content_team`                                                                                                   |
| Operations Systems                | `rpt_tableau__operations_pm`, `rpt_tableau__operations_ekg`                                                                   |
| Stipend and Bonus Dashboard       | `rpt_tableau__stipend_and_bonus_app`                                                                                          |
| Personalized Survey Links         | `rpt_tableau__survey_completion`                                                                                              |
| Federal Grants Timesheet Approval | `docusign_status_feed`                                                                                                        |

Nothing on Tableau Server links a workbook to its table — each of these uses an
**embedded** extract — so this table is the mapping, and it has to be maintained
by hand when a workbook is repointed. Per-workbook variants are listed in the
playbook.

!!! warning "Two archived workbooks still hold pre-migration calculations"

    `Content Team Dashboard` and `Teacher Goals` were archived rather than
    remediated. Restoring either from its archived version brings back the old
    calculation — individual username grants included — and its field references
    no longer match the extracts. Work through its playbook section before
    republishing either one.

### Known gaps

From the 2026-08-05 audit. Each needs a change in Tableau Desktop and a
republish; the working checklist with exact edits is in `.claude/scratch/`,
uncommitted because it names staff usernames.

| #   | Workbook                          | Gap                                                                                                                                                             |
| --- | --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Survey Dashboard                  | `Completion Tracking` and `Individual Tracking` are on the `Home` dashboard and ungated — full roster names, employee numbers, job titles and completion status |
| 2   | Miami Instructional Rubrics       | a correct `Permissions` field exists but is applied at no scope, so both data sheets are ungated                                                                |
| 3   | Survey Dashboard                  | `Permissions - Support` still grants every central office staff member every row, and is the only gate on five sheets                                           |
| 4   | Operations Systems                | `rpt_tableau__operations_ekg` has a group-only gate with no entity or location check, so any school leader sees every school                                    |
| 5   | Federal Grants Timesheet Approval | no permission fields at all. Retirement is in flight                                                                                                            |
| 6   | Leadership Development            | the entity gate has no Paterson branch, so Paterson rows are invisible to Paterson's leadership. Archival is in flight                                          |

The audit also found three dead permission fields, three legacy fields on
SchoolMint Grow that are contained today only because a datasource-wide gate
ANDs over them, and 16 by-name grants. None of those is a live leak. All are in
the playbook's _Known gaps_.

### Related

- Build and repair reference, with all calc text:
  `docs/superpowers/plans/2026-07-31-tableau-workbook-remediation.md`
- Design rationale for each tier and each peer-exclusion helper:
  `docs/superpowers/specs/2026-07-30-tableau-rls-entra-migration-design.md`
- [#4631](https://github.com/TEAMSchools/teamster/issues/4631) — surfaces
  `job_function_code` and fills the missing values, which removes the job-title
  fallbacks throughout
- [#4663](https://github.com/TEAMSchools/teamster/issues/4663) —
  `rpt_tableau__pm_outlier_detection`, deferred out of the migration
- [#4721](https://github.com/TEAMSchools/teamster/issues/4721) — the Survey
  Dashboard department gate, which is expected to take the same peer-exclusion
  shape as Intent to Return
