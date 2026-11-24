# Service playbook skill and capacity board: design

Refs #6497. Sibling of `.claude/skills/project-charter/` (design:
`docs/superpowers/specs/2026-10-27-project-charter-skill-design.md`).

## Intent

Some Data team work never closes. It runs on a yearly cycle of rounds, and each
round repeats the same checklist: Surveys, the Stipend and Bonus App, teacher
performance management, microgoals, O3s and walkthroughs. The `project-charter`
skill covers projects that start and end. Nothing describes the recurring
workstreams in a common shape.

The Data team maps analyst capacity during annual planning. To do that it needs
each recurring workstream described the same way, with an hours estimate, and a
place to hand workstreams to analysts and see who is over or under capacity.

v1 delivers two things:

1. A skill that writes a playbook for a recurring workstream as a Google Doc, in
   the same table format as Walters' charter: what the service is, its rounds
   and steps, and time estimates.
2. A capacity board: a shared page where each analyst has a column of the
   workstreams they are responsible for (their "job description page"), each
   workstream is a card with its hours, and dragging cards between analysts
   updates each analyst's total against their capacity.

## Goals

- The Surveys playbook, as a Google Doc, good enough to hand to a backup owner.
- Hours estimates in a unit that adds up across workstreams: weeks for timing,
  hours per week for load, rolled up to hours per month and per year.
- A board the team can rearrange during annual planning that flags capacity
  mismatches, including seasonal ones (two heavy months landing on one person).

## Non-goals for v1

- Workstreams other than Surveys get no playbook yet. They can appear on the
  board as hand-entered cards with rough hours.
- Rollover: building next year's rounds in Asana and drafting Reporting Terms
  rows. See _Later_.
- Publishing an SLA article to Zendesk. See _Later_.
- A playbook file in the repo. The Google Doc is the playbook in v1.
- Adding hours to `project-charter`'s plan format. That is Walters' skill; raise
  it with him. This design only keeps the units compatible (`duration_weeks`
  plus `hours_per_week`), so chartered projects can join the board later.

## Anti-goals

- Staff or student names in the failure-mode list. The `Tickets + Breakfix`
  history names staff in task titles; the playbook states the failure only.
- A board that looks precise when the hours are guesses. Every estimate the
  skill fills in is marked `[proposed]` until the owner accepts it, and the
  board shows which cards still carry proposed hours.

## Decisions made in the conversation

| Decision        | Choice                                                                                                                                                                                                                                           |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Scope           | Surveys only for the playbook in v1                                                                                                                                                                                                              |
| Granularity     | One playbook per workstream                                                                                                                                                                                                                      |
| Format          | Google Doc, same table style and order as Walters' charter template                                                                                                                                                                              |
| Date source     | Per workstream: the PM calendar (tab `Performance Management <YY-YY>` in the network calendar sheet, `ids.md` row `Network calendar sheet`) for Surveys and teacher performance management; Reporting Terms for microgoals, O3s and walkthroughs |
| Gallup and TNTP | Windows from the PM calendar `SURVEY` column; no Reporting Terms rows (completion is not tracked)                                                                                                                                                |
| Effort unit     | `duration_weeks` plus `hours_per_week` per step                                                                                                                                                                                                  |
| Capacity view   | A hosted claude.ai page with shared saved state, not the MkDocs site (static pages cannot save drags)                                                                                                                                            |
| Board features  | Modeled on the Leader ITR Setup page: drag or click chips between columns, live totals, search, autosave, owner-only controls, read-only for other viewers                                                                                       |

## Approaches considered

For the capacity board:

- **A. Hosted claude.ai page with a shared database (picked).** Drags and
  capacity numbers save for everyone; the skill writes a workstream's card
  directly. Cost: it lives on claude.ai, not in the repo or Drive.
- **B. A page on the MkDocs site.** In the repo and reviewed. Cost: static, so a
  move means a file edit and a PR, which defeats dragging.
- Dropped: a Google Sheet (can total, cannot drag) and Asana Workload (needs a
  paid plan the workspace does not have).

For the playbook, the conversation first chose a repo Markdown file with YAML
front matter, then moved v1 to a Google Doc to match Walters' charter and skip
the publishing pipeline. The repo file returns with rollover (see _Later_).

## Part 1: the playbook doc

### Format

One Google Doc per workstream, named `<Workstream> - Service Playbook`, in a
Drive folder the user names. Tables in Walters' label/value style, in this
order. Sections marked (charter) carry over from his Template 1.

1. SERVICE SUMMARY (charter, adapted): Service name, Owner, Backup, Partner
   team, Asana project, Date source, Hours per year, Busiest months.
2. What the service delivers, and why it matters (charter).
3. Scope: what the Data team supports; what the partner team owns (charter).
4. STAKEHOLDER MAP (charter): who receives or depends on each round.
5. ROLES & OWNERSHIP (charter, MOCHA): Manager, Owner, Consulted, Helper,
   Approver.
6. ROUND CALENDAR: one row per round for the current school year: round, what it
   includes, open week, close week.
7. ROUND CHECKLIST: one row per step: step, anchor (open or close), offset
   weeks, duration weeks, hours per week, role, rounds it applies to.
8. STANDING WORK: load not tied to a round (tickets and breakfix), hours per
   week, which weeks.
9. CAPACITY SUMMARY: hours per month for the school year (July to June) and the
   total. This table is what the board's card shows.
10. SYSTEMS: forms, Zapier zaps, AppSheet, dbt models, Tableau workbooks,
    sheets, each with a link.
11. RAPID DECISION LOG (charter): standing yearly decisions, for example form
    and audience sign-off.
12. KNOWN FAILURE MODES: from the `Tickets + Breakfix` history, failure only.

Every value the skill fills that did not come from the user, Asana or the
calendar starts with `[proposed]`, the same rule as `project-charter`. The user
clears markers; the skill never does.

### How the skill builds it

Input: an Asana project link. The skill reads:

- Project notes and sections: the systems list, the round section.
- Round tasks and their subtasks. These become the round calendar and the
  checklist. Each subtask's due date against its round's window gives the step's
  anchor and offset in weeks.
- `Tickets + Breakfix` tasks: failure modes, stated without names.
- dbt exposures and Tableau workbooks named in the notes, for the systems list.
- The current PM calendar tab, read by tab name through the Sheets API. The tab
  is a free-text weekly grid with merged cells; the skill proposes each round's
  window as open and close weeks and the user confirms before the doc is
  written. The sheet keeps old and revised tabs side by side (for example
  `Performance Management 26-27` and
  `Performance Management 26-27 | updated 9.24`), so the skill asks which tab is
  current.

Hours come from the user. The skill proposes a figure per step, marked
`[proposed]`, and asks the user to correct them in one pass.

The capacity summary is computed, not estimated: for each month, the sum over
steps of `hours_per_week` times the step's working weeks that fall in that
month, plus standing work. Week placement reuses the closure and blocked-week
functions in `.claude/skills/project-charter/scripts/schedule_dates.py` by
import; that file is not edited. For a network-wide workstream, a week is
blocked only when all four regions block it.

Output: the doc link and the capacity summary, shown in chat. Stop for review.
After the user accepts, the skill writes the workstream's card to the board
(Part 2).

## Part 2: the capacity board

### What it shows

- One column per analyst, plus an `Unassigned` column. A column is that
  analyst's "job description page": the workstreams they are responsible for.
- One card (chip) per workstream: name, hours per year, a 12-bar month strip, a
  `proposed` badge when its hours are not yet accepted, and a link to its
  playbook doc when one exists.
- Each column header: the analyst's hours per year against their capacity, and a
  month strip of their summed load. A month over capacity turns the warning
  color; so does the yearly total.
- Search across cards. Click or drag a card to move it, as on the Leader ITR
  Setup page.

### Who can do what

- Everyone with the link sees the board.
- The board owner (and anyone the owner lists as an editor) moves cards, sets
  each analyst's capacity, and adds hand-entered cards. Other viewers see a
  read-only board. This uses the page's knowledge of who is viewing, as the
  Leader ITR page does for its owner-only controls.
- Changes save as they are made, for every viewer.

### Data

Three collections in the page's shared database:

- `workstreams`: `id`, `name`, `hours_by_month` (12 numbers, July first),
  `hours_per_year`, `proposed` (bool), `playbook_url`, `source` (`playbook` or
  `manual`).
- `analysts`: `id`, `name`, `capacity_hours_per_month` (the hours available for
  recurring workstreams, set by the owner).
- `assignments`: `workstream_id`, `analyst_id` (absent means unassigned).

The skill writes a `workstreams` record when a playbook is accepted, and updates
it when the playbook's hours change. It never writes `assignments`; people make
those by dragging.

The page's source lives in the repo with the skill,
`.claude/skills/service-playbook/board/index.html`, so it can be republished to
the same link after a change.

## Constraints

- No PII on the board or in the doc beyond staff names as owner, backup and
  analysts.
- Reuse `project-charter`'s `ids.md` for the calendar sheet; add no duplicate
  ids. The board link and the playbook Drive folder go in this skill's own
  `references/ids.md`, in the same table shape.
- Sheet reads use the Sheets API by tab name, so values have known tab
  provenance.
- The Google Docs connector needs a sign-in in this workspace. If it is
  unavailable when the skill runs, the skill creates the doc through Drive
  instead and says so.

## Left to the builder

- Exact table styling in the doc, matched to Walters' charter copy.
- The board's visual design, following the Leader ITR Setup page's look
  (Whitney, Calibri or Verdana, light and dark themes).
- How the board shows a workstream assigned to two analysts, if that comes up;
  v1 assumes one owner per card.
- Tests for the monthly hours computation.

## Acceptance

- The Surveys playbook doc exists, built from the Asana project `Surveys`
  (`1210036297132224`) and the 2026-27 PM calendar, with every hour the user has
  not yet accepted marked `[proposed]`.
- The board shows a Surveys card whose monthly hours match the doc's capacity
  summary, plus at least the hand-entered cards the user wants for annual
  planning, with each analyst's total updating as cards move.

## Later

Kept from the first draft of this design, for after v1:

- Rollover: each school year, read the playbook and the new calendar, build that
  year's dated round tasks in Asana (skip any that exist, consent step as in
  `project-charter`'s `references/asana-build.md`), draft the Reporting Terms
  rows to paste, and list drift against the previous year.
- The playbook as a repo file (Markdown with YAML front matter) so rollover and
  the board read one machine-readable source.
- An SLA article on Zendesk through the `zendesk-help-articles` skill, generated
  whole from the playbook.
- The Stipend and Bonus App, whose quarterly round dates come from neither the
  PM calendar nor Reporting Terms.
- Chartered projects on the board, once `project-charter` plans carry hours.
