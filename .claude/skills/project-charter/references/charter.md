# Charter

Phase 2. Copy the templates doc, fill Templates 1, 3 and 4 from the brief, and
run the draft against the handbook's failure modes. Ids are in `ids.md`.

## The templates doc

One Google Doc with six tabs, one template per tab. The first line of every tab
says to copy the doc before use; the copy is the project's charter and is never
edited in the original.

| Tab                            | Tables                                                                                                 |
| ------------------------------ | ------------------------------------------------------------------------------------------------------ |
| 1. Project Charter & RAPID log | PROJECT CHARTER (label, value); STAKEHOLDER MAP; ROLES & OWNERSHIP (M, O, C, H, A); RAPID DECISION LOG |
| 2. Work Plan                   | Milestone / Task, Owner, Due Date, Status; `Workstream N: [Name]` and `MILESTONE N: [Name]` label rows |
| 3. Risk Log                    | Risk, Likelihood, Impact, Mitigation, Owner                                                            |
| 4. Stakeholder Engagement Plan | Stakeholder, What They Need From Us, What We Need From Them, Format, Frequency, Relationship Owner     |
| 5. Status Update               | left blank in phase 2                                                                                  |
| 6. Lessons Learned             | left blank in phase 2                                                                                  |

PROJECT CHARTER rows, in order: Project Name, Project Owner, Project Manager,
Start Date, Target End Date, Goal, Why this matters, Scope, Key milestones and
dates, Estimated budget and budget source, Known risks or dependencies. The
short rows have a label cell and a value cell. Goal, Why this matters, Scope,
Key milestones and Known risks are one cell merged across both columns, with the
label paragraph followed by empty paragraphs: the answer goes in the last empty
paragraph of that cell. The title rows of every table are merged the same way.

Writes go through `mcp__claude_ai_Google_Docs__update_doc`, guarded by the
revision id from the read that computed the positions. The read spills to a file
shaped `{content: <document>}`; unwrap `.content` before running the
google-workspace skill's `docs_index.py` on it.

## Steps

1. Ask for the project's Drive folder, or create one under the folder the user
   names. Drive `copy_file` on the templates doc into it, named
   `<Project> - Charter and Plan`. Load `anthropic-skills:google-workspace`
   before this first write.
2. Read the handbook, Part II (the five phases) and Part IV (What Goes Wrong),
   once per session. The doc spills past the tool's size limit; read the spill
   file with `jq` per tab. The handbook is the house standard and this file does
   not restate it.
3. Fill tab 1 from the brief:
   - PROJECT CHARTER: every row. Owner and Manager are people, not teams.
     Milestones get a month in "Key milestones and dates"; phase 3 replaces the
     month with the date. Scope lists what is out as carefully as what is in; a
     stakeholder's "maybe later" goes under out.
   - STAKEHOLDER MAP: one row per group from the brief, power, interest,
     position, concerns, engagement level.
   - ROLES & OWNERSHIP: one name per role, or several Helpers. Consulted and
     Approver are the stakeholder side; they are not project members in phase 4.
   - RAPID DECISION LOG: the two decisions the template asks for (charter and
     scope changes; budget changes), the structural decisions the brief
     surfaced, and one standing row, `Changes after signing`: which roles may
     approve a date, owner or scope edit to the plan without the Manager.
     Default text: Owner for dates; Manager for scope and MOCHA; any member for
     their own Asana tasks. The Manager sets it; the project-assistant follow-up
     reads it before any edit.
4. Fill tab 3 (one risk per row, the template's prompts, a mitigation owner) and
   tab 4 (one row per stakeholder group from the map, a relationship owner
   each).
5. Run the Part IV checks below and write the review message.

Names in MOCHA, RAPID and the engagement plan resolve against the staff roster
for title only, following `intake-brief.md`: name and title, never contact
details.

## Marking

Every sentence that is not a `heard` or `found` line from the brief starts with
`[proposed]`. The user clears the marker when they accept the sentence; the
skill never clears one. The review message ends with the list of `[proposed]`
lines so they can be cleared in one pass.

## Part IV checks

One check per failure mode in the handbook's Part IV. Each finding names the
mode, the row that fails it, and the fix; findings go first in the review
message, before the doc link.

| Failure mode             | Fails when                                                               | Fix                                                        |
| ------------------------ | ------------------------------------------------------------------------ | ---------------------------------------------------------- |
| Jumping to execution     | Goal or Why this matters is blank or restates the ask                    | write the decision the stakeholder makes with the output   |
| Unclear ownership        | Owner, Manager or Approver blank, or a team named where a person goes    | one person per role                                        |
| The forgotten plan       | no milestone has a month, or the end date has no milestone before it     | month per milestone; a close milestone before the end date |
| Stakeholder surprises    | a map row with no engagement-plan row, or an Approver missing from both  | one engagement-plan row per map row                        |
| Scope creep              | Scope has no out-of-scope list, or the RAPID log has no scope-change row | write both                                                 |
| The project never closes | no close milestone, or no lessons-learned session in it                  | add it as the last milestone                               |

## Review message

In order: the Part IV findings, the doc link, the `[proposed]` lines. Then stop.
Phase 3 starts when the user says the milestones and workstreams are right.
