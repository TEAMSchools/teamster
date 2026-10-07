# Gradebook flag triage for central academic ops: design

Issue: [#5782](https://github.com/TEAMSchools/teamster/issues/5782). Date:
2026-10-07. Status: approved in conversation; this is the written spec.

## Goal

Two central academic ops staff can ask Claude in Slack "why does one Q1 Homework
assignment not count for this teacher at this school?" and get the answer the
data team would give: which assignment, which student score, which rule, and
what to change in PowerTeacher Pro. No Zendesk ticket, no data team turn.

## Why now

Four Zendesk tickets in three weeks (485355, 484250, 482587, 482972) each needed
a data team member to query the warehouse for one broken score. The Gradebook
Teacher View shows the category and a reason such as "Invalid scores entered",
but not the assignment or the student. The causes were: a 0 with no Missing flag
in high school; zeros instead of 5s on missing middle school homework; an
assignment set to Percent instead of Points; a shared assignment scored in one
section only; blanks for a student who had left the section.

A probe of the current quarter on 2026-10-07 found a fifth case the tickets
never raised and that will dominate real questions: the plain shortfall, where
fewer assignments are entered than expected and none of them fails a check. In
Newark middle school Summative, for example, 334 of 456 flagged sections were
that case.

## Scope

In scope:

- An end-user Claude skill, `gradebook-flag-triage`, in the private
  `TEAMSchools/ps-plugins` repo beside the existing
  `gradebook-expectations-upload` skill.
- A private Slack channel where Claude in Slack runs that skill against BigQuery
  through a connector attached to that one channel.
- In this repo: a dbt exposure recording the skill as a consumer, and three
  small additions to the `gradebook-audit` Claude Code skill so the data team
  keeps the end-user skill in step with the models.

Out of scope, decided on 2026-10-07:

- Any change to dbt flag logic, Cube, or the Tableau workbook.
- Zendesk ticket reading, reply drafting, or macros. A Zendesk connector for
  claude.ai is a separate issue if the two staff turn out to work tickets.
- Row-level security. This is the short-term path. The long-term path is a Cube
  view with row-level access, a separate issue.

## Decisions

| Decision                         | Choice                                                                                                   | Alternative rejected                 | Why                                                                                                                                                                                                                 |
| -------------------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Data path                        | BigQuery through a Claude in Slack connector                                                             | Cube view with row-level security    | No gradebook cube exists; building one is weeks. The two staff have network-wide legitimate educational interest, so row scoping is not needed for them.                                                            |
| Identity the connector runs as   | A dedicated GCP service account with Data Viewer on the needed datasets and Job User on the project      | The data team director's own account | Anyone in the channel runs any SELECT the identity can. A dedicated account makes the grant the control, keeps job history separate, and survives staff changes. How wide the grant is: see _Security and privacy_. |
| Default answer names the student | Yes, as the ticket replies did                                                                           | Assignment-level counts only         | The teacher has to find the score. The two staff already have the right to see it. Channel is private with short retention; names stay in the channel and the teacher message.                                      |
| Where the skill files live       | ps-plugins                                                                                               | teamster                             | One home for both end-user skills and one shipping procedure. ps-plugins' "no SQL in a skill" rule is scoped to the upload skill; the triage skill's readers run a warehouse connector.                             |
| Drift guard                      | A YAML-only exposure here, plus playbook lines in `gradebook-audit`, plus a column list inside the skill | Nothing in teamster                  | A flag change would otherwise silently break Slack answers. The exposure records lineage; it does not fail on a rename. The column list in the skill is the checklist.                                              |

## How it works

### Surfaces

- **Slack channel** (primary). Private, members: the data team lead, the two
  staff, Claude. The BigQuery connector is added from the channel's own page in
  Claude Tag admin settings so it applies only there. The skill is added to the
  organization library, then attached from the same page. Both documented by
  Anthropic and read on 2026-10-07: Connect BigQuery, Give Claude access to your
  tools, How Claude Tag works.
- **claude.ai chat** (secondary, not set up by default). The skill is in the
  organization library, but a user needs their own BigQuery connector and their
  own dataset access. The install guide tells staff to use the channel unless
  the data team sets them up.

### The loop the skill runs

1. **Lookup.** Resolve the teacher's last name and school to a `teacher_number`,
   `school` and quarter from the dashboard model.
2. **Dashboard rows.** Read the category summary rows and the assignment detail
   rows for that teacher. Branch: healthy; flagged with a reason; flagged with
   no reason (shortfall); a student-grade flag (hand off).
3. **Assignment checks.** One row per assignment from the rollup model, with
   every check boolean and the per-check student counts, plus whether the
   assignment is due by the week cutoff. This is where most answers end.
4. **Student scores.** Only for assignments that need a name: the rows that
   break a rule, with the student's name and section dates from the enrollments
   model, and today's date to tell a current student from one who left.
5. **Message to the teacher.** Good news first, each assignment with the exact
   PowerTeacher Pro action, the count, when the dashboard will show it, a help
   article link where one applies.

Escalation is a fixed hand-off note when the data does not fit the loop: no rows
for the teacher, a null student name, a flag no check explains, or an off-scope
ask.

### Models read

All in `teamster-332318`. Four are intermediates read directly, against the
rpt_-in-between rule, as the short-term path.

| Dataset and model                                                         | Role                                                                   |
| ------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `kipptaf_tableau.rpt_tableau__gradebook_audit`                            | Dashboard rows: category summary and assignment detail; teacher lookup |
| `kipptaf_powerschool.int_powerschool__gradebook_assignment_scores_rollup` | Per-assignment checks and counts; no student data                      |
| `kipptaf_powerschool.int_powerschool__gradebook_assignments_scores`       | Per-student scores and the six per-student checks                      |
| `kipptaf_powerschool.int_powerschool__u_expectations_qtd_unpivot`         | `week_end_sunday`, the cutoff the dashboard counts to                  |
| `kipptaf_extracts.int_extracts__course_enrollments_by_term`               | Student name and section entry and exit dates                          |

The exact columns are listed in the skill's `references/queries.md`. The
templates select the models' own boolean columns rather than restating
thresholds, so a threshold change flows through; a column or label change does
not, and is the maintenance case below.

### Facts the skill encodes that are not obvious from the dashboard

Verified against the model SQL during review on 2026-10-07.

- Detail rows are filtered only on having a flag, not on the week cutoff. An
  assignment due this week appears as failing but is not counted yet; a clean
  one due later is invisible. The checks query carries `counts_by_cutoff`.
- The dashboard's join keeps only `POINTS` and `PERCENT` score types. The checks
  query applies the same filter so letter-grade and collected-only assignments
  do not read as "no scores entered".
- For a `PERCENT` assignment the raw entry is compared against the point value,
  so it trips the above-maximum check. Diagnose the score type first.
- Marking Missing is not enough. The audit reads the score too: 5 in middle
  school, 0 in high school. A middle school Summative marked Missing still has
  to meet the half-points floor.
- `is_expected` means not exempt and counted in the final grade; enrollment on
  the due date comes from the join. An assignment with zero expected students
  counts with no checks.
- A category can meet its number and still carry a flag reason, and a teacher
  can be red from a student quarter grade above 100% or below 70% with no
  comment. The dashboard query selects both booleans.
- A student's `dateleft` is the day they left the section, or the day after the
  term ends while enrolled. A clean section change excludes the old record; an
  unclosed old enrollment can leave a null student name, which the skill hands
  off.
- Scores load nightly and the extract refreshes early morning. A same-day fix
  cannot be confirmed, and the four tickets cannot serve as test fixtures.

## Security and privacy

- The connector's service account has Job User on the project and Data Viewer
  scoped as narrowly as BigQuery allows for these relations. Four of the five
  are views, and BigQuery checks the querying identity against every table a
  view reads. So a plain dataset grant reaches `kipptaf_tableau`,
  `kipptaf_powerschool`, `kipptaf_extracts`, the three district PowerSchool
  datasets, and whatever the dashboard view reads upstream, which together hold
  far more student data than gradebook scores. Two ways to set the grant, for
  the engineer and the FERPA owner to choose between before the runbook's
  dry-run step:
  - **Narrow (preferred):** make the three kipptaf datasets authorized datasets
    on their upstreams, then grant table-level Data Viewer on the five relations
    only. The account can then read exactly those five.
  - **Wide (accepted risk):** dataset-level Data Viewer on the datasets the dry
    run names. Acceptable only because the channel holds two staff with
    network-wide legitimate educational interest, and must be revisited before
    anyone else joins.
- The connector's tokens carry a read-only scope that refuses table creation and
  load jobs regardless of roles. The key is held at Anthropic's proxy and never
  enters Claude's sandbox.
- A daily BigQuery custom quota on the service account bounds a runaway thread.
  Anthropic's Claude Tag spend limit is set separately.
- Student names and scores appear in the channel by design. The channel is
  private, limited to the three people and Claude, with the shortest retention
  the workspace allows. The install guide tells staff to keep names in the
  channel and the teacher message and never in a ticket.
- Every template query starts with `-- gradebook-flag-triage`, so the data team
  can separate these jobs in BigQuery job history.
- The skill is advice to Claude, not an access control. The grants and the
  membership are the controls.

## Deliverables

In `TEAMSchools/ps-plugins`, branch
`anthonygwalters/feat/claude-gradebook-flag-triage`:

- `skills/gradebook-flag-triage/`: `SKILL.md`, `INSTALL.md`,
  `references/queries.md`, `references/reading-the-results.md`,
  `references/message-to-teacher.md`. Version 0.1.0.
- `docs/setup-flag-triage-channel.md`: the data team runbook, from service
  account to acceptance test.
- `scripts/build_skill.py` generalized to every folder under `skills/`; CI
  uploads a `gradebook-flag-triage` artifact; CLAUDE.md, README and
  `ship-a-skill-update.md` describe two skills.

In this repo, on the issue branch:

- `src/dbt/kipptaf/models/exposures/claude.yml`: exposure
  `gradebook_flag_triage_skill` on the five models.
- `.claude/skills/gradebook-audit/`: a routing row and a paragraph in
  `SKILL.md`; a note at the top of `playbooks/change-a-flag.md`; a hand-off line
  in `playbooks/debug-a-flag.md`; the third exposure in
  `playbooks/plan-a-change.md` and `references/data-model.md`.

## Verification

Done so far:

- All four templates run against production on 2026-10-07 and reproduced three
  live cases: a plain shortfall (4 entered of 5), three entirely unscored
  assignments in a high school section, and wrong point values plus a 0 without
  a Missing flag in a middle school section.
- Three independent reviews: one adversarial design review before the build,
  then a SQL-correctness review and an agent-document review after. Every
  finding that changed behavior is listed under _Facts the skill encodes_.
- ps-plugins tests pass (35) and both skill zips build. teamster lint and
  `dbt parse` are clean; the exposure resolves.

Still to do, by the data team, per the runbook:

1. Create the service account and grants; find the full dataset set by dry run.
2. Add the skill to the library; create the channel; attach the connector and
   the skill from the channel's page; verify with "what can you access from this
   channel".
3. Acceptance test built from categories flagged on the day: shortfall, high
   school invalid, middle school invalid, wrong points, half exempt, plus a
   Percent case, a multi-section teacher, a student who left, a first-name ask,
   a no-category ask, a no-rows case, a same-day case, and two off-scope asks.
   Pass criteria are in the runbook.

## Maintenance

A change to a check, a `flag_reasons` label, an `n_*` count, or any column in
the skill's column list updates the skill in the same change, bumps its version,
rebuilds, and re-uploads to the library. New Slack threads pick the new version
up; a running thread keeps the one it started with. The `gradebook-audit`
skill's `change-a-flag` and `debug-a-flag` playbooks carry this rule. A wrong
triage answer is a bug in the skill unless the model is wrong.

## Open items

- Per-request limits for Claude in Slack (result size, tool calls) are not
  documented. The skill carries a row-count guard; if the Slack path truncates
  differently, the guard's wording in `queries.md` is the place to adjust.
- Whether PowerTeacher Pro fills in the missing score automatically when a
  teacher marks a score Missing. The skill says "mark Missing and make sure the
  score reads 5" (or 0), which is correct either way.
- Phase 2: a Cube view with row-level security replacing the BigQuery path, so
  school leaders can ask the same question about their own building. Separate
  issue; the skill keeps data access in one file so the swap is contained.
- If a rename bites before phase 2, the cheap interim guard is a thin contracted
  `rpt_` view over the four intermediates, which is also what the layer rule
  asks for. It would make a rename fail CI and give the service account one
  dataset to read. Not built now because this PR changes no dbt models.
