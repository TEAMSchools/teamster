# Intake brief

Phase 1. Read what the user points at, say what was heard, find what already
exists, and name the gap. The brief is the user's to take back to the
stakeholder; nothing in it is quoted from the source material.

## Sources

Read every item the user names, in whatever mix. Record each one's title and
date for the brief's source list.

| Material           | Tool                                                                                                               | Pass                                     | Pull                                                                              |
| ------------------ | ------------------------------------------------------------------------------------------------------------------ | ---------------------------------------- | --------------------------------------------------------------------------------- |
| Meeting transcript | Granola `search_meetings`, then `get_meetings`; `get_meeting_transcript` only when the notes leave the ask unclear | the meeting title or date the user gives | who asked, the decision they need, what they described, timing, what they use now |
| Meeting transcript | Wispr Flow `search_meetings`, then `get_meeting`; a shared link through `resolve_share_link`                       | same                                     | same                                                                              |
| Email thread       | Microsoft 365 `outlook_email_search`; Gmail tools when that connector is on                                        | the subject or sender and a date range   | same, plus any attachment named                                                   |
| Slack thread       | Slack `slack_read_thread`                                                                                          | the permalink                            | same; a thread's reactions are not a decision                                     |
| Doc or mockup      | Drive `read_file_content`; a Sheet through Sheets `get_values`, one call per tab                                   | the link or id                           | the fields, filters and groupings the mockup shows                                |
| Zendesk ticket     | invoke `zendesk-tickets`                                                                                           | the ticket number                        | the ask and its history; the thread text stays in that skill's test file          |
| Pasted text        | none                                                                                                               |                                          | same as a transcript                                                              |
| Scratchpad file    | Read                                                                                                               | the path                                 | same as a transcript                                                              |

Every claim pulled from a source is tagged `heard`. A transcript line about a
student or family becomes the data need it implies ("families need to see
attendance by week"), never the detail.

## Extraction

Answer these five in the stakeholder's own terms, one short paragraph each, each
sentence tagged `heard`:

1. Who asked, and for whom.
2. The decision they are trying to make with it.
3. What they described wanting (the view, the numbers, the groupings).
4. What they said about timing, and why that date.
5. What they said they already use for this.

Where the material does not answer one, write "not said" and carry it into the
questions section.

## Inventory

Run in this order; each line of the result names the asset and how it was found,
tagged `found`.

1. Tableau: `mcp__tableau__search-content` with the ask's two or three strongest
   terms, then `get-workbook` on each dashboard the stakeholder named. Record
   workbook, view, owner.
2. Cube: `mcp__claude_ai_Cube__meta`; list the views whose measures or
   dimensions cover what was asked.
3. dbt: the exposure and lineage sweep in
   `.claude/skills/model-support/references/intake-and-inventory.md`, sections
   "Find the consumers" and "Propose the boundary". Add marts under
   `src/dbt/kipptaf/models/` whose names match the ask's terms (`ls` on the mart
   folders; no build).
4. Open work: `mcp__github__search_issues` with `repo:TEAMSchools/teamster` and
   the ask's terms; `mcp__claude_ai_Asana__search_tasks` on the Data team's
   projects. Both drift, so the brief marks these lines `lead`, not `found`.
5. Support history: BigQuery `execute_sql_readonly` on
   `kipptaf_marts.fct_support_tickets`, counting tickets by category and month
   for the surface terms the stakeholder used, last two school years. Themes and
   counts only; no ticket text, no requester.

## The brief

A markdown file in the session scratchpad, `brief-<project>.md`, shown in full
in chat, in this order:

1. Sources read: title and date, one per line.
2. What we heard: the five extraction answers.
3. What exists today: the inventory lines, each with its tag and how found.
4. The gap: what the ask needs that nothing in section 3 gives, and what in
   section 3 the stakeholder may not know about.
5. Questions for the stakeholder: everything marked "not said", plus any place
   where sections 2 and 3 disagree.
6. Size, one line: `task`, `small project` or `project`, with the handbook's
   test applied (defined start and end, a deliverable, more than one person's
   work).

Staff appear by name and title, from the staff roster when the material gives
only a first name; never contact details. Nothing about a student or family.

Offer once, in the stop message, to save the brief as a Google Doc in the
project's Drive folder. Do not create one unasked; the user decides what the
stakeholder sees.
