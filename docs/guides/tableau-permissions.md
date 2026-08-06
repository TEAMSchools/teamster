# Tableau Permissions

How row-level security works on our Tableau workbooks — who can see whose data,
and how it is implemented.

This page has two halves. **Part 1** is for anyone who wants to understand or
question what they can see, and needs no Tableau knowledge. **Part 2** describes
the field structure and points at the build reference.

**Status: live** on nine workbooks, listed in Part 2. One caveat is called out
inline where it applies: the support surveys are not yet scoped by department.

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
them.** This is the most complicated gate in the network, so it is worth reading
from both sides.

#### If you answered, who sees it

| If you are                                       | Your answers reach                                                                                                                                                                        |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A teacher or learning specialist                 | Your manager, your school's assistant principals, your school leader and director of school operations, your regional leadership, and the HR, Recruiting and Leadership Development teams |
| An assistant school leader                       | Your manager, your school leader and director of school operations, your regional leadership, and those three teams — **not** other assistant principals                                  |
| A school leader or director of school operations | Your manager, your regional leadership, and those three teams — **not** other school leaders or DSOs                                                                                      |
| A departmental director                          | Your manager, your region's senior leadership, and those three teams — **not** other directors in your department                                                                         |
| Regional leadership                              | Your manager and those three teams — **not** other regional leaders                                                                                                                       |
| Central office staff                             | Your manager and those three teams. No regional leader sees central office answers                                                                                                        |

#### If you are a viewer, what you see

Seven routes, and the peer exclusion differs on each because "your own level"
means something different depending on where you sit.

| Route | Who                                                                                                                                                                   | Reaches                                          | Minus                                                                                                                  |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| 1     | You, and the manager recorded on the response                                                                                                                         | that response                                    | nothing — a manager sees their report even when both are director-rank                                                 |
| 2     | The administrators of the process — the data, HR, and Recruiting teams, and the Leadership Development team (the group of that name, not the workbook being archived) | everything, network-wide                         | nothing                                                                                                                |
| 3a    | Managing directors of school operations, heads of schools, managing directors of operations                                                                           | your region                                      | regional-leadership respondents. Directors stay visible — you sit above them                                           |
| 3b    | The Syndicate                                                                                                                                                         | your region                                      | regional leadership, and director-rank peers — **except** school operations directors, who are your own line of report |
| 3c    | School Support Directors                                                                                                                                              | your region                                      | regional leadership, and every director rank                                                                           |
| 4     | School leaders and directors of school operations                                                                                                                     | your school                                      | each other                                                                                                             |
| 5     | Assistant principals                                                                                                                                                  | teachers and learning specialists at your school | everyone else at that school                                                                                           |
| 6     | Special Education Directors, KIPP Forward Directors                                                                                                                   | your own department, in your own region          | director-rank peers. Associate directors stay visible                                                                  |
| 7     | TEAM Council                                                                                                                                                          | everyone, network-wide                           | chief-level respondents                                                                                                |

Routes 3a, 3b and 3c look redundant and are not. They are three groups sitting
at three different heights, so one shared exclusion would hide the wrong people:
a managing director should still see their directors, while a Syndicate member
should not see director-rank peers — but should still see the school operations
directors who report to them.

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

#### Three limits worth knowing

These are accepted, not undiscovered. Each is a place the gate is approximate.

- **The council shield hides chief-level titles, not council membership.**
  Tableau can only ask which groups the _viewer_ belongs to, never the
  respondent, so route 7's exclusion has to be inferred from job title. If the
  council includes heads of schools or managing directors — and it plausibly
  does — their answers stay visible to fellow council members: 720 rows from 23
  people hold a senior title that is not chief level.
- **Miami's KIPP Forward staff have no departmental viewer.** Route 6 is scoped
  by region, and Miami has KIPP Forward respondents but no KIPP Forward director
  of its own, so those answers reach only their manager and the route-2 teams.
- **Two titles cannot be ranked from text.** Bare `Fellow` and bare `Director`
  say nothing about seniority on their own, so the peer exclusions cannot place
  them. [#4631](https://github.com/TEAMSchools/teamster/issues/4631) replaces
  every title test with a job-function code and removes this whole class of
  guesswork.

### The support surveys are not department-scoped yet

The Survey Dashboard's KTAF support sheets — the ones asking staff to rate how
well a central office department supports them — are gated by entity, region and
school, and **not** by the department being rated. Two consequences today:

- Every member of the central office staff group sees **every** row, including
  feedback about departments other than their own.
- A viewer who reaches the sheets by any other route sees every department's
  feedback for the rows they can reach, not just their own department's.

!!! note "Planned: department scoping"

    The fix is to carry the department each question rates through to the extract
    and add a department gate, so a viewer sees feedback about their own
    department and the blanket central-office grant can be removed.
    [#4721](https://github.com/TEAMSchools/teamster/issues/4721) is the issue and
    [#4728](https://github.com/TEAMSchools/teamster/pull/4728) the open PR.

    **This has not shipped.** The PR carries only the data layer and is blocked on
    two things outside the repo — Ops adding the department columns to the
    form-items sheet, and a decision on how merged departments resolve to a single
    code. Until both land and the workbook is edited, the behaviour above is what
    is live. Treat department scoping as future state.

    The rated department cannot be parsed out of the question name: it exists only
    as a prefix across three inconsistent naming schemes, and departments have
    merged over time. It has to come from data.

### The walkthrough sheets scope by the school walked

On Operations Systems, a row from the Operations EKG walkthrough form is about
**the school that was walked**, not about the person who filled the form in. So
school leaders and DSOs see their own school's walkthroughs regardless of who
carried them out — and they do not see walkthroughs they carried out at other
schools.

The broader operations groups — the data team, TEAM Council, managing directors
and the Syndicate — see every region here on purpose, because walkthroughs are a
cross-regional practice.

!!! note "If a school looks like it has no walkthroughs"

    Check the round before assuming this is a permissions problem. The dashboard can
    be filtered to a single walkthrough round for everyone at once, and a school that
    has only ever had a different round then shows nothing at all. That filter sits on
    the data source, so it appears on no sheet's filter shelf.

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
invisible to anyone auditing group membership, and they survive the person
changing roles.

---

## Part 2 — What the fields are

Row-level security is implemented as Tableau calculated fields inside each
workbook. This section is enough to read a workbook and know what you are
looking at. It is not enough to build one.

**To build, repair, or audit a workbook, use the playbook** —
`docs/superpowers/plans/2026-07-31-tableau-workbook-remediation.md`. It carries
the paste-ready text of every field, the order to create them in, how to resolve
field names, where to attach the filter, the per-workbook variants, the
verification personas, and the outstanding work. Calc text lives only there, so
the two cannot drift.

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

They are separate fields rather than one calculation because the entity gate is
needed by two different routes, because a per-workbook difference becomes a
one-line edit to a small field instead of surgery inside a long one, and because
each gate can be put on a sheet by itself and compared against a row — which is
how you find out why someone sees the wrong thing.

**The gates read group membership, never the viewer's own roster row.** That is
what makes cross-entity supervision work: someone employed by TEAM who oversees
Paterson schools gets Paterson visibility by being added to the Paterson group,
with no change to any workbook.

A workbook can hold **more than one** permission field, where particular sheets
need a different rule — the Survey Dashboard has two, SchoolMint Grow has more.
So "the `Permissions` field is correct" does not by itself mean a workbook is
correctly gated, and the per-sheet answer is in the playbook rather than here.

### The gated workbooks

Nine workbooks carry a `Permissions` field. All sit in the `Production` project
and all are tagged `entra-ready` on Tableau Server. **That tag is the
inventory** — a gated workbook without it is either unfinished or was built
without following the playbook.

| Workbook                    | Datasource                                                                                                                    |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Manager Survey Reports      | `rpt_tableau__manager_survey_details`                                                                                         |
| Manager Survey Rollup       | `rpt_tableau__manager_survey_details`                                                                                         |
| Coaching Conversation Tool  | `rpt_tableau__schoolmint_grow_observation_details`                                                                            |
| SchoolMint Grow Dashboard   | `rpt_tableau__schoolmint_grow_observation_details`, `rpt_tableau__schoolmint_grow_goals`, `rpt_tableau__teacher_observations` |
| Survey Dashboard            | `rpt_tableau__survey_responses`, `rpt_tableau__survey_completion`                                                             |
| Miami Instructional Rubrics | `rpt_tableau__content_team`                                                                                                   |
| Operations Systems          | `rpt_tableau__operations_pm`, `rpt_tableau__operations_ekg`                                                                   |
| Stipend and Bonus Dashboard | `rpt_tableau__stipend_and_bonus_app`                                                                                          |
| Personalized Survey Links   | `rpt_tableau__survey_completion`                                                                                              |

Two workbooks are leaving this list. Federal Grants Timesheet Approval now reads
a live Google Sheet rather than a dbt extract, so it has no gated datasource;
Leadership Development is becoming archive-only as leader performance management
moves to Lattice. Neither is a gap. Until they are retired, Leadership
Development is also one of three workbooks that shield senior leaders from each
other, which then becomes two.

Nothing on Tableau Server links a workbook to its table — each of these uses an
**embedded** extract — so this table is the mapping, maintained by hand when a
workbook is repointed. Per-workbook variants, and the two archived workbooks
that predate this model, are in the playbook.

### Related

- Build, repair, and audit reference, with all calc text and the outstanding
  work: `docs/superpowers/plans/2026-07-31-tableau-workbook-remediation.md`
- Design rationale for each tier and each peer-exclusion helper:
  `docs/superpowers/specs/2026-07-30-tableau-rls-entra-migration-design.md`
- [#4631](https://github.com/TEAMSchools/teamster/issues/4631) — replaces every
  job-title test with a job-function code, which removes the title fallbacks
  this page describes as approximate
- [#4721](https://github.com/TEAMSchools/teamster/issues/4721) — department
  scoping for the support surveys
