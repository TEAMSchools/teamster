---
name: service-playbook
description:
  Use when a recurring, cyclical Data team workstream needs describing or sizing
  ("playbook for surveys", "describe this recurring workstream", "time estimates
  for <workstream>", "how many hours is <workstream>", "add <workstream> to the
  capacity board", "capacity board"). Not for a project that starts and ends;
  that is `project-charter`.
---

# Service playbook

Two phases, each ending with its output shown and a stop. Phase 2 runs only
after the user accepts the playbook doc. Procedure lives in `references/`; this
file is the order and the rules that hold everywhere.

## Size test

A service runs every school year in rounds and never closes (Surveys, teacher
performance management, microgoals). Work with a start, an end and a deliverable
is a project: hand it to `project-charter` and stop.

## Non-negotiables

- Read `references/ids.md` and
  `.claude/skills/project-charter/references/ids.md` first in every session. A
  row marked `UNSET` blocks the phase that uses it until the user supplies the
  value.
- No student or family data anywhere. Staff appear by name only as owner,
  backup, Manager, Approver and analysts. A failure mode states the failure,
  never the person, even when the Asana task title names someone.
- Every value that did not come from the user, Asana or the calendar starts with
  `[proposed]`. The user clears the marker; the skill never does.
- Every write to Drive or the board happens after the user has seen what will be
  written.
- No tool call string contains the bare token `env`.

## Phases

1. **Playbook doc.** Read `references/playbook-doc.md`. Input: an Asana project
   link. Output: the doc link and the capacity summary. Stop. Continue when the
   user accepts the doc or says to put it on the board as it stands.
2. **Board card.** Read `references/board.md`. Output: the card as written and
   the board link. Stop; the skill is done.

## Starting mid-way

When a playbook doc already exists, ask for its link, read it, and confirm in
one line which sections it holds before running the phase asked for. Phase 2 on
an existing doc reads the CAPACITY SUMMARY table and the `[proposed]` markers;
it does not recompute.
