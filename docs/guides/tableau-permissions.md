# Tableau Permissions — People Data Dashboards

The Tableau developer reference for row-level security on the dashboards built
from **people data** — staff surveys, observations, coaching, compensation, and
operations walkthroughs. It records exactly who can see whose data, and how the
workbooks implement it.

**Staff asking what they can see, or how to get access, belong on the help
center article instead:**
[How to access Tableau](https://teamschools.zendesk.com/hc/en-us/articles/360009686434).
It carries the plain-language version of Part 1 and the request steps. When
behavior changes, update both.

Student-data dashboards are **not** governed by this page. The nine workbooks
listed in Part 2 are the full scope: every row in each of them is about a member
of staff.

**Part 1** is the behavior reference: the routes, the per-workbook differences,
and the exact group names. **Part 2** describes the field structure and points
at the build reference.

**Status: live** on nine workbooks, listed in Part 2. Last checked against the
calculations in the published workbooks on 2026-09-29.

---

## Part 1 — Behavior reference

Access is decided **per row**, from the viewer's Tableau group membership, never
from their job title or roster row. So access changes by changing a group, with
no workbook edit.

### The five ways you can be shown a row

You see a row if **any one** of these is true. They are additive.

|     | Route                    | You see                                                                                           |
| --- | ------------------------ | ------------------------------------------------------------------------------------------------- |
| 1   | **You, or your manager** | Your own row. Your direct reports' rows.                                                          |
| 2   | **A network-wide group** | Everything, for a small number of functional groups such as the data team and Employee Relations. |
| 3   | **Regional operations**  | Your region's rows, if you are in a regional ops group.                                           |
| 4   | **Regional leadership**  | Your region's rows, if you are a regional leader.                                                 |
| 5   | **Your school**          | Your school's rows, if you are in that school's staff group _and_ hold a role that permits it.    |

Route 5 needs all three of the right entity, the right school, and a qualifying
role. Missing any one of them means no access by that route. On most workbooks
an assistant principal's route 5 reaches only the teachers and learning
specialists at their school, not every row there.

Most workbooks follow these five routes exactly. The ones that do not are listed
under _Where a workbook differs_.

!!! note "A sixth route exists for one named group"

    `Paterson TEAM Staff` reaches both Paterson Prep schools' rows directly,
    without the three-part route-5 test. Membership of the group is itself the
    qualification, and it is scoped to the same rows a school leader or director
    of school operations at those schools would see.

    It works this way because the remit spans both Paterson schools rather than
    sitting at one of them. It is the only group scoped like this; everyone else
    goes through routes 1 to 5.

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

!!! note "The exception: Survey Dashboard completion tracking"

    On the completion tracking sheets the central office group sees every row in
    every region, other central office staff included. This is deliberate.

    The support sheets start from the same grant but limit central office staff
    to the questions about their own department. See _The support surveys are
    scoped by the department being rated_.

### Senior leaders are shielded further

On Manager Survey Reports, Manager Survey Rollup and Leadership Development,
rows about chief-level staff are hidden from TEAM Council. Most chiefs sit on
TEAM Council, so this is what stops them seeing each other's rows. The rows stay
visible to the person, their manager, and the data, Employee Relations and
Leadership Development groups. A central office chief's row is outside the
regional routes already, so those are the only people who see it.

Seniority is read from the ADP job function rather than from job title text, so
a newly created senior title is covered automatically without anyone editing a
workbook.

Where the job function is missing, a job-title fallback applies instead: chief
titles, president, and executive director. The job function is missing on most
historical rows, so the fallback does the work on older data rather than being a
rare edge case. It is deliberately a shade broader than the job function itself,
which places executive directors and deputy chiefs one tier below chief level.

### Senior leaders' stipends are shielded wider

The Stipend and Bonus Dashboard hides a larger group, from more routes. Stipends
paid to anyone whose job function is chief level, "EDs, HOSs, MDOs", or "KTAF or
Regional Managing Director" are hidden from TEAM Council, regional operations,
regional leadership and school-based viewers.

They stay visible to the person, their manager, and the data and Employee
Relations groups, which process payments. Where the job function is missing,
titles containing chief, president, managing director, head of schools or
executive director count instead.

### Where a workbook differs

| Workbook                          | Difference from the five routes                                                                                                                                                                                                                                                                                                                                                                                                                 |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Coaching Conversation Tool        | You see your own observations only once they are released: a score form once it is locked, other observations once the coaching-conversation window opens. Observations outside a tracked cycle show straight away. Your manager sees them immediately.                                                                                                                                                                                         |
| SchoolMint Grow Dashboard         | Route 1 is your manager only. Your own observations are in the Coaching Conversation Tool. The norming sheets widen route 4: school leaders see their whole region on every norming sheet, and APs and DSOs see their region on the summary norming sheets. On the norming sheets that name individual teachers, APs and DSOs stay at their own school.                                                                                         |
| Survey Dashboard                  | Three gates, one each for Intent to Return, the support surveys and completion tracking. Intent to Return has its own section below. Support and completion tracking have no route 1, grant central office every region (limited to their own department on the support sheets), and add region-wide access for Teaching and Learning, Technology, School Support Directors and Special Education Directors. APs see every row at their school. |
| Operations Systems                | The performance-management sheets follow the five routes, but APs do not qualify for route 5. The walkthrough sheets work differently; see _The walkthrough sheets scope by the school walked_.                                                                                                                                                                                                                                                 |
| Stipend and Bonus Dashboard       | The stipend shield above. The HR download sheets are narrower still: only the data and Employee Relations groups see them.                                                                                                                                                                                                                                                                                                                      |
| Miami Instructional Rubrics       | New Teacher Development sees everything. NTN coordinators qualify for route 5 alongside school leaders, DSOs and APs.                                                                                                                                                                                                                                                                                                                           |
| Personalized Survey Links         | Your own link only. Nobody else sees it, including your manager.                                                                                                                                                                                                                                                                                                                                                                                |
| Leadership Development (archived) | Only school leaders qualify for route 5.                                                                                                                                                                                                                                                                                                                                                                                                        |

### The Intent to Return survey is different

Intent to Return answers reach fewer people than anything else on Tableau, and
who they reach depends on your own level. **Nobody at your own level ever sees
them.** This is the most complicated gate in the network, so it is worth reading
from both sides.

#### If you answered, who sees it

| If you are                                       | Your answers reach                                                                                                                                                                                        |
| ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A teacher or learning specialist                 | Your manager, your school's assistant principals, your school leader and director of school operations, your regional leadership, and the Employee Relations, Recruiting and Leadership Development teams |
| An assistant school leader                       | Your manager, your school leader and director of school operations, your regional leadership, and those three teams — **not** other assistant principals                                                  |
| A school leader or director of school operations | Your manager, your regional leadership, and those three teams — **not** other school leaders or DSOs                                                                                                      |
| A departmental director                          | Your manager, your region's senior leadership, and those three teams — **not** other directors in your department                                                                                         |
| Regional leadership                              | Your manager and those three teams — **not** other regional leaders                                                                                                                                       |
| Central office staff                             | Your manager and those three teams. No regional leader sees central office answers                                                                                                                        |

Two audiences are on every row above and are easy to miss. **The data team**
administers the survey and reaches every response. **TEAM Council** reaches
every response too, with one exception — answers from chief-level staff, which
it does not see.

#### If you are a viewer, what you see

Eight routes, and the peer exclusion differs on each because "your own level"
means something different depending on where you sit.

| Route | Who                                                                                                            | Reaches                                          | Minus                                                                                                                  |
| ----- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| 1     | You, and the manager recorded on the response                                                                  | that response                                    | nothing — you see your own answers, and your manager sees yours, even when you are both director-rank                  |
| 2     | The administrators of the process — the Data, Employee Relations, Recruiting, and Leadership Development teams | everything, network-wide                         | nothing                                                                                                                |
| 3a    | Managing directors of school operations, heads of schools, managing directors of operations                    | your region                                      | regional-leadership respondents. Directors stay visible — you sit above them                                           |
| 3b    | The Syndicate                                                                                                  | your region                                      | regional leadership, and director-rank peers — **except** school operations directors, who are your own line of report |
| 3c    | School Support Directors                                                                                       | your region                                      | regional leadership, and every director rank                                                                           |
| 4     | School leaders and directors of school operations                                                              | your school                                      | each other                                                                                                             |
| 5     | Assistant principals                                                                                           | teachers and learning specialists at your school | everyone else at that school                                                                                           |
| 6     | Special Education Directors, KIPP Forward Directors                                                            | your own department, in your own region          | director-rank peers. Associate directors stay visible                                                                  |
| 7     | TEAM Council                                                                                                   | everyone, network-wide                           | chief-level respondents                                                                                                |
| 8     | Paterson TEAM Staff                                                                                            | both Paterson Prep schools                       | school leadership, the same people a Paterson school leader cannot see                                                 |

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

- **The TEAM Council shield hides chief-level titles, not council membership.**
  Tableau can only ask which groups the _viewer_ belongs to, never the
  respondent, so route 7's exclusion has to be inferred from job title. A
  council member whose title is senior but not chief level therefore stays
  visible to fellow members.
- **Miami's KIPP Forward staff have no departmental viewer.** Route 6 is scoped
  by region, and Miami has KIPP Forward respondents but no KIPP Forward director
  of its own, so those answers reach only their manager and the route-2 teams.
- **Two titles cannot be ranked from text.** Bare `Fellow` and bare `Director`
  say nothing about seniority on their own, so the peer exclusions cannot place
  them. [#4631](https://github.com/TEAMSchools/teamster/issues/4631) replaces
  every title test with a job-function code and removes this whole class of
  guesswork.

### The support surveys are scoped by the department being rated

The Survey Dashboard's support sheets ask staff to rate how well a central
office department supports them. Each of those questions is tagged with the
department it rates. What you see depends on where you sit.

| You are                                                                                                                                 | You see                                                                                                      |
| --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| School-based leadership — school leader, DSO, AP, or `Paterson TEAM Staff`                                                              | Every question, every department, for your own school                                                        |
| Regional staff outside central office — regional ops, AcOps, School Support Directors, Special Education Directors, regional Technology | Your own department's questions, for your region. Nothing else — not the questions that rate no department   |
| Central office staff                                                                                                                    | Your own department's questions, from every region. Nothing else — not the questions that rate no department |

For regional and central office staff, the department test applies **on top of**
entity, region and school. Belonging to the Operations group does not show you
Operations feedback from a region you cannot otherwise reach — both tests have
to pass. The central office group passes the entity, region and school tests for
every row, so for central office staff the department is the only thing that
narrows. Anyone outside school-based leadership who is in no department group
sees nothing on these sheets.

Four groups see every department regardless: the data team, TEAM Council,
managing directors of school operations, and heads of schools. The last two sit
across departments, so scoping them to one would hide most of what they oversee.
On these sheets TEAM Council is `KNJ-SG-Tableau TC`, not the `Group Staff TC`
group the other workbooks use.

#### The department groups

For central office and regional staff: ask for the one matching the department
whose feedback you need to read. School-based leadership does not need one.

| Department rated                     | Group                                               |
| ------------------------------------ | --------------------------------------------------- |
| Compliance                           | `KNJ-SG-Tableau All Compliance`                     |
| Data                                 | `KNJ-SG-Tableau All Data`                           |
| Development                          | `TS-DL-Advancement`                                 |
| Finance, including Purchasing        | `TS-SG-R9 Finance` or `TS-SG-R9 Purchasing`         |
| Human Resources - Employee Relations | `Group Staff Employee Relations`                    |
| Leadership Development               | `KNJ-SG-Tableau All Leadership Development`         |
| Marketing, Comms and Enrollment      | `KNJ-SG-Tableau All Marketing Comms and Enrollment` |
| Operations                           | `KNJ-SG-Tableau All Operations`                     |
| Real Estate and Facilities           | `TS-SG-R9 Facilities`                               |
| Special Education                    | `KNJ-SG-Tableau Special Education Directors`        |
| Talent Acquisition                   | `KNJ-SG-Tableau All Recruiting`                     |
| Teacher Development                  | `KNJ-SG-Tableau All New Teacher Development`        |
| Teaching and Learning                | `KNJ-SG-Tableau All T&L`                            |
| Technology                           | `TS-SG-R9 Technology`                               |

!!! note "Questions that rate no department"

    Some questions rate the organisation rather than a department — whether your
    region is headed in the right direction, and the free-text boxes asking for
    any other feedback. Those carry no department, so nobody who is scoped by
    department sees them. They reach only school-based leadership, for their own
    school, and the four groups above that see every department.

!!! warning "The support sheets do not show respondent names, and that is not
the same as anonymous"

    The department gate drops the respondent-name question from every support
    sheet, so none of them displays a respondent's name. Treat that as the
    normal reading experience rather than as a guarantee, because two things sit
    outside it.

    The underlying data still carries the name, along with employee number and
    email. Tableau has no way to hide a column from someone who can download the
    data or edit the workbook on the web, so those two permissions reach it
    whatever any sheet shows. Web editing also lets a person take the permission
    filter off a sheet, which is why that permission is the one worth being
    careful with.

    And a respondent can name themselves inside their own free-text answer.
    Nothing in the permissions model can strip that. Anyone who can reach the
    row can read the words in it.

### The walkthrough sheets scope by the school walked

On Operations Systems, a row from the Operations EKG walkthrough form is about
**the school that was walked**, not about the person who filled the form in. So
school leaders and DSOs see their own school's walkthroughs regardless of who
carried them out — and they do not see walkthroughs they carried out at other
schools.

The broader operations groups — the data team, TEAM Council, managing directors
and the Syndicate — see every region here on purpose, because walkthroughs are a
cross-regional practice.

### Rooms do not grant access

Working in a Room — the office locations rather than a school — does not grant
visibility of that Room's occupants. Room-based staff reach data through the
network-wide and regional-leadership routes instead.

This matters because Rooms are shared: Room 9 has occupants from more than one
entity, so treating a Room like a school would hand people access across entity
lines.

### No by-name grants

Individual, by-name grants inside a workbook are **not permitted**. They are
invisible to anyone auditing group membership, and they survive the person
changing roles. Grant access by group only. One by-name grant is still live, on
the Stipend and Bonus Dashboard's HR download sheets, and is tracked for removal
in the playbook linked in Part 2.

### Group names

These are the exact names the calculations test. `ISMEMBEROF` against a name
that does not exist cannot fail loudly: the branch never matches, so the viewer
sees nothing and there is no error to chase. Check a new name against the
Tableau site's group list before putting it in a calculation.

#### Your entity — everyone has one

| Entity                        | Group                                   |
| ----------------------------- | --------------------------------------- |
| TEAM (Newark)                 | `KNJ-SG-Tableau All Staff TEAM Schools` |
| KIPP Cooper Norcross (Camden) | `KNJ-SG-Tableau All Staff KCNA`         |
| KIPP Miami                    | `KNJ-SG-Tableau All Staff MIA`          |
| KIPP Paterson                 | `KNJ-SG-Tableau All Staff Paterson`     |
| Central office                | `KNJ-SG-Tableau All Staff KTAF`         |

#### Your school

The rule is `KNJ-SG-Tableau All Staff ` followed by the school name — **with
five exceptions where the group kept an older name**. Ask for the group in the
right column, not the name in the left.

| School                          | Group                                                     |
| ------------------------------- | --------------------------------------------------------- |
| KIPP BOLD Academy               | `KNJ-SG-Tableau All Staff KIPP BOLD Academy`              |
| KIPP Cooper Norcross High       | `KNJ-SG-Tableau All Staff KIPP Cooper Norcross High`      |
| KIPP Courage Academy            | `KNJ-SG-Tableau All Staff KIPP Courage Academy`           |
| KIPP Hatch Middle               | `KNJ-SG-Tableau All Staff KIPP Hatch Academy`             |
| KIPP Justice Academy            | `KNJ-SG-Tableau All Staff KIPP Justice Academy`           |
| KIPP Lanning Square Middle      | `KNJ-SG-Tableau All Staff KIPP Lanning Square Middle`     |
| KIPP Lanning Square Primary     | `KNJ-SG-Tableau All Staff KIPP Lanning Square Primary`    |
| KIPP Legacy Elementary          | `KNJ-SG-Tableau All Staff KIPP Legacy Elementary`         |
| KIPP Legacy Middle              | `KNJ-SG-Tableau All Staff KIPP Legacy Middle`             |
| KIPP Life Academy               | `KNJ-SG-Tableau All Staff KIPP Life Academy`              |
| KIPP Miami - North Campus       | `KNJ-SG-Tableau All Staff KIPP Miami - North Campus`      |
| KIPP Miami - Poinciana Campus   | `KNJ-SG-Tableau All Staff Poinciana Campus`               |
| KIPP Miami Technical High       | `KNJ-SG-Tableau All Staff KIPP Miami Technical High`      |
| KIPP Newark Collegiate Academy  | `KNJ-SG-Tableau All Staff KIPP Newark Collegiate Academy` |
| KIPP Newark Lab High School     | `KNJ-SG-Tableau All Staff KIPP Newark Lab High School`    |
| KIPP Purpose Academy            | `KNJ-SG-Tableau All Staff KIPP Purpose Academy`           |
| KIPP Rise Academy               | `KNJ-SG-Tableau All Staff KIPP Rise Academy`              |
| KIPP Royalty Academy            | `KNJ-SG-Tableau All Staff KIPP Royalty Academy`           |
| KIPP SPARK Academy              | `KNJ-SG-Tableau All Staff KIPP SPARK Academy`             |
| KIPP Seek Academy               | `KNJ-SG-Tableau All Staff KIPP Seek Academy`              |
| KIPP Sumner Elementary          | `KNJ-SG-Tableau All Staff KIPP Sumner Academy`            |
| KIPP TEAM Academy               | `KNJ-SG-Tableau All Staff KIPP TEAM Academy`              |
| KIPP THRIVE Academy             | `KNJ-SG-Tableau All Staff KIPP THRIVE Academy`            |
| KIPP Upper Roseville Academy    | `KNJ-SG-Tableau All Staff KIPP Upper Roseville Academy`   |
| Paterson Prep Elementary School | `KNJ-SG-Tableau All Staff KIPP Paterson Prep Elementary`  |
| Paterson Prep Middle School     | `KNJ-SG-Tableau All Staff KIPP Paterson Prep Middle`      |

The five where the names differ are Hatch, Poinciana, Sumner, and both Paterson
Prep schools.

Rooms are deliberately absent — see _Rooms do not grant access_.

#### Your role — needed for route 5, on top of entity and school

| Role                          | Group                    |
| ----------------------------- | ------------------------ |
| School leader                 | `KNJ-SG-Tableau All SL`  |
| Director of school operations | `KNJ-SG-Tableau All DSO` |
| Assistant principal           | `KNJ-SG-Tableau All AP`  |
| NTN coordinator               | `TS-DL-NTN Coordinators` |

The NTN coordinator group qualifies on Miami Instructional Rubrics only. Which
roles qualify on the other workbooks is in _Where a workbook differs_.

#### Paterson-wide remits

| Who                                                        | Group                 |
| ---------------------------------------------------------- | --------------------- |
| School-leader-equivalent across both Paterson Prep schools | `Paterson TEAM Staff` |

This one grants on its own — no entity or school group is needed alongside it,
because the two Paterson Prep locations belong to KIPP Paterson and nobody else.
Note it has no `KNJ-SG-Tableau` prefix; that is the real name.

#### Regional operations and leadership

| Who                                    | Group                                        |
| -------------------------------------- | -------------------------------------------- |
| NJ regional operations                 | `Group Staff NJ Regional`                    |
| Miami regional operations              | `Group Staff MIA Regional`                   |
| Managing director of school operations | `KNJ-SG-Tableau All MDSO`                    |
| Head of schools                        | `KNJ-SG-Tableau All HOS`                     |
| Managing director of operations        | `KNJ-SG-Tableau All MDO`                     |
| Academic operations                    | `KNJ-SG-Tableau AcOps`                       |
| The Syndicate                          | `KNJ-SG-Tableau The Syndicate`               |
| School support directors               | `KNJ-SG-Tableau School Support Directors`    |
| Special education directors            | `KNJ-SG-Tableau Special Education Directors` |
| KIPP Forward directors                 | `KNJ-SG-Tableau KIPP Forward Directors`      |
| Teaching and Learning                  | `KNJ-SG-Tableau All T&L`                     |
| Technology                             | `TS-SG-R9 Technology`                        |

The last two are region-wide on the Survey Dashboard's support and completion
sheets only, and both also rate as a department on the support sheets.
`KNJ-SG-Tableau All T&L` matches the roster's Teaching and Learning department
exactly. Use it rather than `NJ Teaching and Learning` or `Teaching & Learning`,
which cover only part of the department.

#### Network-wide functional groups

These grant broadly and are not added on request from an individual — they
follow from the function you sit in.

| Group                                        | Sees everything on                                                                                                            |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `KNJ-SG-Tableau All Data`                    | every workbook except Personalized Survey Links                                                                               |
| `Group Staff Employee Relations`             | every workbook except Operations Systems, Personalized Survey Links, and the Survey Dashboard's support and completion sheets |
| `Leadership Development`                     | Manager Survey Reports and Rollup, Coaching Conversation Tool, SchoolMint Grow, Miami Instructional Rubrics, Intent to Return |
| `Group Staff TC` (TEAM Council)              | most workbooks; see the senior-leader and stipend shields                                                                     |
| `KNJ-SG-Tableau TC` (TEAM Council)           | the Survey Dashboard's support and completion sheets                                                                          |
| `KNJ-SG-Tableau All Recruiting`              | Intent to Return                                                                                                              |
| `KNJ-SG-Tableau All New Teacher Development` | Miami Instructional Rubrics                                                                                                   |

!!! note "Not every workbook grants every group"

    The network-wide list above is the one tier that legitimately differs per
    workbook, so membership of one of these does not guarantee access to all nine.
    The entity and school groups behave the same way everywhere.

---

## Part 2 — What the fields are

Row-level security is implemented as Tableau calculated fields inside each
workbook. This section is enough to read a workbook and know what you are
looking at. It is not enough to build one.

**To build, repair, or audit a workbook, use the playbook** —
`docs/superpowers/plans/2026-07-31-tableau-workbook-remediation.md`. It carries
the paste-ready text of every field, the order to create them in, how to resolve
field names, where to attach the filter, the per-workbook variants, the
verification personas, and the outstanding work. Calc text lives only there, not
on this page. The playbook can still fall behind the workbooks: where the two
disagree, the published workbook is what runs, so audit from its `.twbx`.

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
need a different rule. So "the `Permissions` field is correct" does not by
itself mean a workbook is correctly gated, and the per-sheet answer is in the
playbook rather than here.

| Workbook                    | Permission fields                                                                                                       |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Survey Dashboard            | `Permissions - Completion`, `Permissions - Support` with `RLS - Department Gate` beside it, `Permissions - ITR`         |
| SchoolMint Grow Dashboard   | `Permissions`, `Permissions - Norming`, `Permissions  - Norming - Individual Data` (two spaces before the first hyphen) |
| Stipend and Bonus Dashboard | `Permissions`, `Permissions HR Download`                                                                                |
| Operations Systems          | one `Permissions` per datasource, with different text                                                                   |
| Personalized Survey Links   | `Permissions - Self` only, with none of the gate fields                                                                 |

### The gated workbooks

Nine workbooks carry a `Permissions` field. All sit in the `Production` project
and all are tagged `entra-ready` on Tableau Server. **A gated workbook without
that tag is either unfinished or was built without following the playbook.**

The reverse does not hold. Querying the tag returns **11**, not nine, because
the two workbooks described below the table carry it as well. The table is the
inventory; the tag is a superset of it.

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

Two workbooks sit outside the table. Federal Grants Timesheet Approval reads a
live Google Sheet rather than a dbt extract, so it has no gated datasource.
Leadership Development is archive-only, leader performance management having
moved to Lattice; it is one of three workbooks that shield senior leaders from
each other. Neither is a gap.

Each of these uses an **embedded** extract rather than a published datasource,
so this table is the readable mapping. It is not the only one: Tableau Server
does report a workbook's upstream datasources, embedded ones included, so the
table can be checked against the server rather than trusted on faith. Do check
it after any repoint — a repoint that adds the new datasource without detaching
the old one leaves both attached, and only the server shows that. Manager Survey
Rollup is in that state now: `int_surveys__manager_survey_details` is still
attached with its old permission fields, though no sheet reads it. Per-workbook
variants, and the two archived workbooks that predate this model, are in the
playbook.

### Related

- Build, repair, and audit reference, with all calc text and the outstanding
  work: `docs/superpowers/plans/2026-07-31-tableau-workbook-remediation.md`
- How to read and change these calculations programmatically, and how to
  republish without dropping the `entra-ready` tag this page treats as the
  inventory: the `tableau-workbook-xml` skill
- Design rationale for each tier and each peer-exclusion helper:
  `docs/superpowers/specs/2026-07-30-tableau-rls-entra-migration-design.md`
- [#4631](https://github.com/TEAMSchools/teamster/issues/4631) — replaces every
  job-title test with a job-function code, which removes the title fallbacks
  this page describes as approximate
