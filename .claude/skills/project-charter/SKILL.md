---
name: project-charter
description:
  Use when a stakeholder ask needs to become a project ("charter this", "new
  project", "turn this transcript into a plan", "write the intake brief", "build
  the work plan", "set up the Asana project"), whatever the material (a meeting
  transcript, an email thread with a mockup, a Slack thread, a Zendesk ticket,
  several together). Not for a single dashboard change or a ticket; those are
  tasks, and the size test below says so.
---

# Project charter

Four phases, each ending with its output shown and a stop. The next phase runs
only when the user says the earlier output is right. Procedure lives in
`references/`; this file is the order and the rules that hold everywhere.

## Size test

A project has a defined start and end, a deliverable, and more than one person's
work. A single dashboard change, a model fix or a ticket is a task: say so, name
where it goes (a GitHub issue, the Zendesk reply), and stop. When it is unclear,
ask one question rather than guess.

## Non-negotiables

- Read `references/ids.md` first in every session. A row marked `UNSET` blocks
  its phase; a calendar sheet for another school year blocks phase 3.
- Source material is PII. Staff appear by name and title; nothing about a
  student or family reaches the brief, the doc, Asana, a GitHub issue, a PR or a
  commit, and no line of a transcript, thread or ticket is quoted into any of
  them. `.claude/rules/ferpa-pii.md` applies.
- Every claim in the brief and the charter carries its origin: `heard`, `found`,
  `lead`, or `[proposed]`. The user clears `[proposed]`, never the skill.
- Every write to Drive, Docs or Asana happens after the user has seen what will
  be written. Bulk `create_tasks` follows the consent step in
  `references/asana-build.md`.
- No tool call string contains the bare token `env`.

## Phases

1. **Intake brief.** Read `references/intake-brief.md`. Input: whatever the user
   points at. Output: the brief in the session scratchpad, shown in full. Stop.
   Continue when the user says the brief is right and has the stakeholder's
   answers, or says to proceed on stated assumptions.
2. **Charter.** Read `references/charter.md`. Output: the filled copy of the
   templates doc, the Part IV findings and the `[proposed]` list. Stop. Continue
   when the user says the milestones and workstreams are right.
3. **Work plan and dates.** Read `references/scheduling.md`. Output: the dated
   plan written into the doc, with the rule that placed each date. Stop.
   Continue when the user approves the plan.
4. **Asana project.** Read `references/asana-build.md`. Output: the project link
   and the counts against the plan. Stop; the skill is done.

## Starting mid-way

A session may start at any phase when the earlier outputs exist. Ask for the
charter doc link, read it, and confirm in one line what the doc already holds
before running the phase asked for.
