# Project charter skill — design

Refs [#6154](https://github.com/TEAMSchools/teamster/issues/6154).

## Problem

A data team project starts when a stakeholder hands over an ask: a meeting
transcript, an email thread with a mockup, a Slack thread, a Zendesk ticket, or
several of those together. Turning that into a project today is hand work for
the project manager: read the material, check what Tableau, dbt and Cube already
cover, fill in the six KTAF Project Management Templates, pick dates that dodge
regional breaks, and build the Asana project section by section. The Claude/Cube
plan for SY26-27 took weeks of this and is the worked example of what the output
should look like. That project is already in motion and is not a target for the
skill.

The skill's job is the next project, and the one after that.

## Intent

A `project-charter` skill that takes a stakeholder ask and produces, in order
and with a review stop between each:

1. An intake brief: what we heard, what exists today, the gap, and the questions
   only the stakeholder can answer.
2. A filled copy of the Project Management Templates doc: charter, stakeholder
   map, MOCHA, RAPID log, risk log and stakeholder engagement plan.
3. A work plan with owners and Friday due dates that skip the breaks of every
   region in scope.
4. An Asana project in the Data team, created from a saved Asana project
   template, with one section per workstream, a milestone per milestone, and the
   work plan's tasks underneath.

The brief exists so that no charter is written on a misread ask. The review
stops exist because each phase feeds the next and the user is the only one who
can say the earlier one is right.

## Goals, non-goals, anti-goals

Goals:

- A fresh session can run every phase on a real ask with nothing in context but
  the skill and the material the user points at.
- The skill reads the current template doc, handbook and calendar each time,
  instead of restating them. When the PMO changes a template, the skill follows.
- Every date in the work plan is a Friday outside any in-scope region's break,
  and the user can see which rule placed it.
- The Asana project matches the shape the team settled on for Claude/Cube:
  governance section first, numbered workstream sections, milestones as Asana
  milestones, tasks with owners and dates.

Non-goals:

- Running the project after kickoff: status updates (Template 5), weekly work
  plan upkeep, lessons learned (Template 6). Those are follow-ups once the
  intake path has been used twice.
- Spinning off a project-specific skill for large projects. Separate design; see
  Follow-ups.
- Replacing the handbook. The skill points at it.

Anti-goals, the ways this fails while technically working:

- A charter that reads well but asserts things the stakeholder never said. Every
  claim in the brief and charter is marked as heard, found, or proposed.
- A plan whose dates land on a break because the calendar link went stale.
- Student or family details from a transcript reaching a Google Doc, an Asana
  task, or GitHub.

## Constraints

- Transcripts and threads are PII-bearing: staff names, sometimes families or
  students. The brief and charter name staff by name and title. Nothing about a
  student or family goes into any output; a transcript line about a student is
  summarized as the data need it implies. Nothing from the source material is
  quoted in a GitHub issue or PR. The rules in `.claude/rules/ferpa-pii.md`
  apply.
- The network calendar sheet gets a new link every year. The skill cannot
  hard-code it.
- The Google Drive tools flatten a Sheet into one text blob with no tab names.
  Tab-level reads need the Sheets tools, which have a per-minute read quota that
  one burst of 3 calls already hit during design. Reads are one call per tab,
  spaced.
- `mcp__claude_ai_Asana__create_tasks` `html_notes` rejects `<p>` and `<br>`;
  `custom_fields` is a JSON-encoded string; bulk `create_tasks` needs the user's
  consent restated in plain text in the same turn, per the root CLAUDE.md. The
  Asana conventions file injects on first use and carries the rest.
- No tool call text may contain the bare token `env`; the hooks deny it.
- The charter copy lives in Google Drive only. There is no markdown twin in the
  repo: a second copy drifts, and the Google Doc is what stakeholders sign.
  Later sessions re-read it by id.

## Approaches

Three were considered after dropping one skill per phase (four Asana-aware
skills reading one shared state is more upkeep than value).

- **A. One phased skill plus an Asana project template.** `project-charter` runs
  four phases with a stop after each. The Asana structure that does not change
  between projects (team, custom fields, the governance and parking-lot
  sections) is a saved Asana project template made once by hand. The skill
  creates from it and adds workstream sections, milestones and tasks. Reference
  files carry the ids of the template doc, the handbook, the calendar sheet and
  the Asana template, so the prose stays short. Trade-off: one broad trigger,
  and a session that starts at phase 4 reads the charter doc first.
- **B. Two skills with a file handoff.** `project-charter` through the work
  plan, writing a markdown charter into the repo; `asana-project` reads it and
  builds Asana. Sharper triggers and reusable for projects chartered elsewhere.
  Trade-off: two skills to keep aligned, a file-format contract, and a repo copy
  of every charter.
- **C. As A, but the skill builds every Asana section itself.** No template to
  maintain in Asana, but section names and custom-field GIDs become prose in the
  skill, which is what drifts.

**Selected: A.** The user picked it in brainstorming. B becomes worth it only if
people outside this skill start chartering projects that need the Asana half.

## Phases

Each phase ends by showing its output and stopping. The next phase runs only
when the user says so. A session may start at any phase if the earlier outputs
exist; the skill asks for the charter doc link when it does.

### Phase 0: size the ask

The handbook's test: a project has a defined start and end, a deliverable, and
more than one person's work. A single dashboard change or a ticket is a task,
and the skill says so and stops. When it is unclear, the skill asks one question
rather than guessing. This is one short paragraph in `SKILL.md`, not a phase
with an output.

### Phase 1: intake brief

Input: whatever the user points at. Transcripts through the Granola or Wispr
Flow tools by meeting name or link; email through the Microsoft 365 or Gmail
tools; Slack threads through the Slack tools; mockups and docs through Drive;
Zendesk tickets through the `zendesk-tickets` skill; pasted text; files in the
session scratchpad. The skill lists what it read, with title and date, at the
top of the brief. Source material explains intent; it is never quoted into the
brief.

Extraction, in the stakeholder's own terms: who asked and for whom, the decision
they are trying to make, what they described wanting, what they said about
timing, and what they said they already use.

Inventory, in this order:

1. Tableau: `mcp__tableau__search-content` on the ask's terms, then the
   dashboards the stakeholder named. Record workbook, view, and owner.
2. Cube: `mcp__claude_ai_Cube__meta` for views that already carry the measures.
3. dbt: the exposure and lineage sweep from
   `.claude/skills/model-support/references/intake-and-inventory.md`, "Find the
   consumers" and "Propose the boundary". Marts under `src/dbt/kipptaf/models/`
   whose names match the ask's terms.
4. Open work: `mcp__github__search_issues` with the ask's terms, and
   `mcp__claude_ai_Asana__search_tasks` on the Data team's projects. Both drift;
   the brief records them as leads, not facts.
5. Support history: the warehouse copy of Zendesk tickets, through the BigQuery
   tool, for the surface terms the stakeholder used. Themes only, no ticket
   text.

Output: a markdown brief in the session scratchpad, shown in full in chat, with
five sections: what we heard, what exists today, the gap, questions for the
stakeholder, and a one-line size call (task, small project, project). Each line
in "what exists today" names the asset and how it was found. The skill offers to
save the brief as a Google Doc in the project's Drive folder; it does not do so
unasked. My call: the brief is for the user to take back to the stakeholder, so
it is theirs to send.

### Phase 2: charter

Precondition: the user says the brief is right and has the stakeholder's
answers, or says to proceed on stated assumptions.

Steps:

1. Ask for the project's Drive folder, or create one under the folder the user
   names. Copy the "Project Management Templates" doc into it with
   `mcp__claude_ai_Google_Drive__copy_file`, named
   `<Project> - Charter and Plan`.
2. Read the Project Management Handbook, Part II (the five phases) and Part IV
   (What Goes Wrong), once per session. The handbook is the house standard; the
   skill does not restate it.
3. Fill Template 1 (charter, stakeholder map, MOCHA, RAPID log) from the brief.
   Milestones get month-level targets here; exact dates come from phase 3. Scope
   lists what is out as carefully as what is in. Every sentence that is a
   proposal rather than something heard or found is marked `[proposed]` so the
   user can clear them on review. Names in MOCHA and RAPID are resolved against
   the staff roster for title only, following the intake reference's rule: name
   and title, never contact details. The RAPID log gets one standing row,
   "changes after signing": which roles may approve a date, owner or scope edit
   to the plan without the Manager (default: Owner for dates, Manager for scope
   and MOCHA, any member for their own Asana tasks). The Manager sets it here,
   and the project-assistant follow-up reads it before applying any edit.
4. Fill Template 3 (risk log) and Template 4 (stakeholder engagement plan).
   Templates 5 and 6 stay blank: they are filled during and after the project.
5. Run the draft against Part IV of the handbook. Each failure mode becomes one
   check: a charter without an Owner and an Approver fails "unclear ownership";
   a scope with no out-of-scope list fails "scope creep"; a plan with no close
   milestone fails "the project never closes". The check's findings go at the
   top of the review message, before the doc link.

Writing the doc uses the Google Docs update tool. The `google-workspace` skill
loads before the first Drive or Docs write.

Output: the doc link, the failure-mode findings, and the list of `[proposed]`
lines.

### Phase 3: work plan and dates

Precondition: the charter's milestones and workstreams are approved.

The skill builds Template 2 rows: milestone or task, owner, due date, status.
Workstreams come from the charter, one per lane with its owner; every task sits
under a milestone and every milestone under a workstream.

Date rules, applied by a small script so they are the same every time. These
follow what the Claude/Cube work plan did by hand, where a single closed day
(Veterans Day observed) stayed a due date but whole-week closures were skipped:

- Due dates are Fridays.
- A week is blocked when any region in the project's scope has a closure of 3 or
  more consecutive weekdays in it, per the "Important Dates/Federal Holidays"
  tab of the network calendar sheet, which has a Yes/No column per region.
  Blocked weeks are skipped: they do not count toward a duration. A single
  closed day does not block its week. The skill reads that one tab with the
  Sheets tool and passes the rows to the script.
- Thanksgiving week is blocked whole, whatever the tab says, because half the
  regions are out from Wednesday and the rest all week.
- A Friday that is a closed day for any in-scope region moves to the Thursday.
- The last milestone is project close, with the lessons-learned session, and it
  lands before the target end date in the charter.
- A date past the last row of the calendar tab is placed by the Friday and
  Thanksgiving rules alone and marked `unverified: calendar not published` in
  the note column. The skill tells the user to re-run phase 3 for those rows
  once the next year's sheet exists. `ids.md` holds one calendar link at a time.

The script, `scripts/schedule_dates.py`, takes the breaks table as CSV, the
regions in scope, the project start date, and one row per milestone and task:
workstream, name, duration in working weeks, and an optional `after` naming the
row it follows. A row with no `after` starts at the project start, so
workstreams run in parallel by default and a cross-workstream dependency (ops
starts when assessments is verified) is one `after`. The script dates every row,
milestones and tasks alike, and prints the table with the rule that placed each
date. It has offline tests. The user can override any date; the override is
recorded in the note column and later rows that follow it shift with it.

Output: the dated work plan written into Template 2 of the charter doc, and the
charter's milestone table updated with the exact dates. The script's input rows
(workstream, name, duration, `after`, override notes) go into the doc too, as a
"Schedule inputs" table after the plan, so a later re-run can start from them
instead of reverse-engineering dependencies from the dated table. See the
project-assistant follow-up.

### Phase 4: Asana project

Precondition: the work plan is approved.

1. Create the project from the saved Asana project template with
   `mcp__claude_ai_Asana__create_project_from_template`, in the Data team,
   private, named as the charter names the project. The template carries the
   Domain, Active and Priority custom fields and the fixed sections:
   `0 · Governance` and `Parking lot and outside the core set`.
2. Add one section per workstream, numbered in the charter's order:
   `1 · <workstream>`, `2 · <workstream>`.
3. Add members: the project team only, meaning the MOCHA Manager, Owner and
   Helpers plus the user. Consulted and Approver names are stakeholders, not
   members; they get status updates, not a private Data team project. Resolve
   each name to an Asana user with `mcp__claude_ai_Asana__search_objects`
   (`resource_type: user`) by name, and confirm the match in the review message.
   No email comes from the staff roster.
4. Create one milestone task (`resource_subtype: milestone`) per milestone, in
   its workstream's section, with owner and due date. Create the work plan's
   tasks under their section with owner and due date, and set each one's parent
   to its milestone. A task that already exists as a GitHub issue is named
   `#NNNN | title`, the TEAMster convention, so it can be multi-homed into
   TEAMster later without renaming.
5. Set the project's Domain field from the charter's stakeholder group and
   Active to `Active`. Write the charter doc link into the project description,
   so the project is the one place a later session starts from.

Before step 4 the skill shows the full task list and asks for a yes. After the
yes it restates the consent in plain text in the same turn before calling
`create_tasks`, per the root CLAUDE.md consent rule.

Output: the project link and a count of sections, milestones and tasks created,
checked against the work plan.

The Asana project template is made once by hand by the user: a project in the
Data team with the three custom fields and the two fixed sections, saved as a
template. The skill's reference file carries its GID. The build plan includes a
step for this, and the skill refuses to run phase 4 until the GID is filled in.

## Skill layout

```text
.claude/skills/project-charter/
  SKILL.md                     triggers; the size test; the four phases with
                               their stop points; PII and consent rules
  references/
    ids.md                     template doc, handbook, PMO folder, calendar
                               sheet link and tab name (updated at rollover),
                               Asana template GID, Data team GID, custom field
                               and option GIDs
    intake-brief.md            source tools per material type; extraction
                               prompts; inventory order; brief format
    charter.md                 template copy and fill rules; [proposed]
                               marking; name resolution; the Part IV check list
    scheduling.md              date rules; how to read the breaks tab; script
                               usage; override recording
    asana-build.md             template create; sections; milestones and
                               parents; member resolution; custom field values
  scripts/
    schedule_dates.py          date placement, no network

tests/project_charter/
  test_schedule_dates.py       Fridays; blocked weeks per region; Thanksgiving
                               whole week; holiday Friday to Thursday; close
                               before end date; override note
```

`SKILL.md` description triggers: "new project", "project charter", "charter
this", "turn this transcript into a plan", "work plan", "set up the Asana
project", "intake brief", a stakeholder ask handed over with a request to plan
it. It does not trigger on a single task or ticket; the size test in phase 0
sends those elsewhere.

`references/ids.md` is the only file with ids in it. Its calendar line reads as
a rollover procedure: when the sheet's title year no longer matches the school
year, ask the user for the new link and update the line. The builder finds the
Drive and Asana ids by name, then the user confirms every line of the file
before any live test; a wrong id would sit silently in the one place that holds
ids.

## What is left to the builder

- The exact prompts in `intake-brief.md` for each source tool, and how the brief
  lists sources.
- The wording of the `[proposed]` marker and whether it survives into the signed
  doc or is cleared on approval. Default: cleared on approval, by the user.
- The CSV shape the script takes for the breaks table, as long as the tab's rows
  map to it without hand editing, and how a date range like `Dec 21 - Jan 1` in
  the tab is parsed.
- Whether `create_tasks` sets the milestone parent in the same call or needs a
  second `update_tasks` pass. Verify against the tool, not the docs.
- The Drive folder convention for charters. Default: the user names the parent
  folder each time.

## Testing

- Offline: `uv run pytest tests/project_charter`.
- Live, during the build, once per phase on one real ask the user supplies, with
  the Asana project created under a `TEST ·` prefix in the Data team and
  archived by hand afterward (no delete tool). The reference files get a
  "Verified live" note with the date for each tool surprise found.
- A fresh-session run of all four phases before the PR leaves draft.

## Follow-ups

- Status update drafting (Template 5) from the Asana project's state, and
  lessons learned (Template 6) at close. Natural phases 5 and 6; add after two
  projects have gone through intake.
- If a second team starts chartering through this skill, revisit approach B.

### Follow-up: project-assistant

The ask, in the user's frame: a junior PM for each chartered project. Any team
member hands it new material (a follow-up meeting, an email thread, a Slack
thread, a mockup) or asks it where the project stands, and it keeps the charter,
work plan and Asana project current, notices what a PM would notice, and
recommends. The first idea was one spun-off skill per large project, shared
through the repo and retired at close. Sketch below, with the pushback, so the
direction can be judged now; the design is its own brainstorm after this skill
has run on one real project.

A junior PM's duties, as the skill would carry them:

- Take in new material and say what it changes: what it adds to or contradicts
  in the charter (scope, MOCHA, milestones, risks, decisions), one proposed edit
  per line, each marked doc, plan or Asana.
- Keep the plan honest: when a date moves, re-run the date script so followers
  shift; when an owner changes, update MOCHA and task assignees together; when a
  task closes late, say what it pushes.
- Run the Part IV checks every time it is invoked, not only when material
  arrives: tasks overdue or unowned, milestones with nothing under them,
  decisions pending past their date, a stakeholder who has not been told
  something that affects them, scope that drifted in without a charter edit.
  Each finding names the failure mode it matches.
- Draft, never send: the project team meeting agenda (what closed since last
  time, what is due before next time, the decisions pending and who owns them,
  the findings below that need a person), the Template 5 status update, the
  stakeholder-facing explanation of a slip, the question to put to an owner. The
  human sends. The agenda is the most frequent of these and the one the checks
  feed most directly, so it is the first draft type to build.
- Recommend with a reason: a date change, a scope line to the parking lot or
  into a charter revision, a risk to add, a re-sign when the edits pile up.

What it must not do: edit the charter or plan without a yes from the invoking
person, message any stakeholder, or decide. It reports to whoever invoked it.

What this needs, split by kind:

- Procedure: everything above. The same for every project.
- Project context: the charter doc, the work plan and its schedule inputs, the
  Asana project, the regions in scope, the decision log. Differs per project and
  is already written down in Drive and Asana by phases 2 to 4. The Asana project
  description holds the charter link; the charter holds the rest.

Pushback on the per-project skill: it would carry only the second kind, and a
skill is the wrong container for it. One PR to create and one to retire per
project, a body that is the same boilerplate every time, and a trigger that
collides with every other open project's ("where are we on the plan" matches all
of them). The one thing a per-project skill could carry that nothing else does
is project-specific procedure, like the Claude/Cube verification subtasks. That
case exists but is rare, is hand-written, and is what the repo's domain skills
already are; it does not fall out of a charter.

Pushback on the junior PM frame: a junior PM has a cadence; a skill acts only
when invoked. Nobody invokes a check that is not on their mind, so the overdue
and unowned findings surface only when someone brings material. The fix is not a
scheduled agent that edits (it cannot take a yes), but a scheduled read-only
digest, the Part IV checks across every Active Data team project posted to the
data team Slack channel, with the edits left to a person who then invokes the
skill. That is a third piece, and it can wait until the skill exists.

Proposed shape: one generic `project-assistant` skill, a sibling of this one,
sharing `references/` and the date script. Trigger: new material about a named
project, "where are we on", "update the charter", "the stakeholder wants to
add", "this date slipped", "draft the agenda", "draft the status update", "what
does this change". Flow: find the Asana project by name, follow its description
to the charter, read any new material with the phase 1 source tools, run the
checks, produce a project brief (findings with their failure mode, proposed
edits one per line, drafts), then apply the approved lines. Every team member
runs it on their own Drive and Asana credentials, so no per-project setup; what
a member needs to join a project is its name. Retiring a project is the Asana
archive and nothing in the repo.

What this changes in the current build: phase 3 writes the schedule inputs into
the work plan doc, and phase 4 writes the charter link into the Asana project
description. Both are in the phases above. Everything else waits.

Who may approve what is not open: the charter's "changes after signing" row
(phase 2) sets it per project, and the assistant refuses an edit the invoker may
not approve and drafts it for the role that may.

Open until the brainstorm: whether the charter's RAPID log is enough of a
decision record or the doc needs a dated change log; how many edits before the
skill proposes a charter revision and a re-sign; whether the scheduled digest is
worth a scheduled-agent PII review.

## Revision 2026-10-28: the Asana project template

The first live run showed the template the skill pointed at was the Data team's
product template, built for a data product after launch: eight sections, 25
placeholder tasks, a project-local Priority field. A chartered project starts
and ends, so the skill now creates from a template made for that: three fixed
sections (`0 · Governance`, `Handoff`, `Parking lot and outside the core set`),
eight standing tasks drawn from the handbook (charter signed, kickoff, weekly
team meeting, status update, close and lessons learned; name the owner after
close, help article or training, comms to affected staff), the three network
fields, and no workstream sections. Phase 3's plan carries the governance and
handoff rows as standard rows; phase 4 dates the standing tasks in place, adds
the workstream sections through the project update call, and creates only the
plan's own milestones and tasks. The template's import file lives with the skill
as `references/asana-template.csv`. The product template keeps its role for
products in service; the handoff section points at it.

## Out of scope

- Budget tables beyond the charter's one line.
- Any write to TEAMster or to a GitHub project board.
- Calendar invites or scheduling meetings.
