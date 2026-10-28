---
name: cube-validation-answers
description:
  'Use when someone asks to answer a Cube validation review or its questions:
  "answer the attendance review", "walk me through issue #N", "answer the
  validation questions", or a "Validate <dashboard> in Cube" issue waiting on
  the owner''s answers.'
---

# cube-validation-answers

This runs in the owner's session. The owner knows the policy, is not a coder,
and answers here in chat. A "Validate <dashboard> in Cube" issue in
`TEAMSchools/teamster` holds the owner's questions; one comment from the owner
carries the answers, and the analyst records them. The owner never edits
validation files or runs the validator, and neither does this session.

## Rules

- Read the questions only from the issue's fenced `json` block, never from its
  markdown.
- Speak in policy words. Name a column, member or file only when the owner asks.
- The owner's checks are theirs to run, independent of Claude. Show the steps
  and the SQL; never run the pinned SQL for them.
- **Example students or staff the owner asks to see come from the owner's own
  access, through the BigQuery console or the BigQuery MCP
  `execute_sql_readonly`, and stay in the owner's chat.** Nothing posted carries
  a student's name, number or row, or a staff member's name, email or row:
  counts and codes only, counts under 10 as `<10`.
- Post nothing until the owner confirms its text.

## Steps

1. Find the issue: the number the owner gave, else an open issue titled
   "Validate <dashboard> in Cube" for the dashboard they named
   (`mcp__github__search_issues`); if several match, ask which. Read it with
   `mcp__github__issue_read` and parse its one fenced `json` block: a list of
   questions, each with `id`, `reason`, `decisions`, `views`, `definitions`,
   `evidence`, `counts`, `hand_checks`, `moment`, `expires` and `expired`. Read
   its comments too: skip a question an earlier answers comment of the owner's
   already covers, unless they want to change it, and then send them to the
   analyst.
2. Say how many questions there are. A question with `expired: true` has pinned
   SQL that no longer runs: the owner can answer without the checks, or wait for
   the analyst to re-run so they work. For the wait, offer to draft a short
   comment on the validation issue asking the analyst to re-run, posted only on
   the owner's confirmation. When `expires` is within 1 day, say when the checks
   stop working, so the owner runs them first.
3. Ask one question at a time, with everything up front, in this order:
   1. The question in policy words ("Which attendance codes should count as
      tardy?"), built from `reason` and `counts`, with no column names.
   2. Both definitions side by side (`definitions.dashboard` and
      `definitions.cube`), code groups spelled out.
   3. Who differs: the filters on each side, and the rows and students only one
      side counts, by school or grade, from `counts` as given.
   4. What triage found (`evidence`) and why it is the owner's call.
   5. The owner's checks, one per `hand_checks` entry. The dashboard: the sheet
      (`sheet` in `workbook`), every filter to set there (`filters`), the cell
      to read (`dims`, or the total), and the number to expect (`dashboard`)
      beside Cube's (`cube`). `<10` on a rate or average is a whole value under
      10, such as a rate of 0 or 1 (0% or 100%), masked by rule. Then each
      side's SQL (`dashboard_sql`, `cube_sql`) in a fenced `sql` block to paste
      into the BigQuery console, with its dry-run price (`dashboard_usd`,
      `cube_usd`): it is pinned to the run's moment and returns only that cell.
      Tableau shows its last refresh, so a small difference may not match there.
      An entry with `none` has no group cell to show: offer to find an example
      under the owner's access, in this chat.
   6. The choices, with what happens next, plus free text:

      | Choice                     | `call`          | What happens next                                 |
      | -------------------------- | --------------- | ------------------------------------------------- |
      | The dashboard is right     | `fix_cube`      | Cube is fixed under the domain's Cube-fix issue   |
      | Cube is right              | `fix_dashboard` | the domain's Asana dashboard-fix task             |
      | Both fine, intended        | `deliberate`    | recorded; later runs stay quiet on it             |
      | The source data is wrong   | `fix_source`    | a new GitHub issue for that data's owner (step 5) |
      | Free text ("need to talk") | `domain_owner`  | stays open, with the owner's note in the decision |

4. Answer a follow-up from the same evidence (the question's JSON, the
   validation file, the owner's BigQuery access), say so when it does not answer
   it, then ask the question again with its choices.
5. For "the source data is wrong", draft a GitHub issue for that data's owner in
   the shape of `.github/ISSUE_TEMPLATE/bug_report.md`: the question, both
   definitions, the counts, the owner's note and what this session found, as
   counts and codes, with `Refs #<validation issue>`. Leave out every student
   and staff detail, including ones the owner looked at here. Ask the owner whom
   to assign; the data's owner is named only as the GitHub assignee, never in
   the body. Show the owner the full text and open it with
   `mcp__github__issue_write` on their confirmation. Its `#<number>` is that
   answer's `task`.
6. At the end, show a summary of the answers: each question, the choice, the
   note. Notes become decision reasons in git, so check each for a student's or
   staff member's name, an email, or an ID or phone number, and ask the owner to
   reword any (dates and school years are fine). If the owner stops early, the
   summary covers only what they answered; the rest wait for a later session.

## The answers comment

On the owner's confirmation, post 1 comment with
`mcp__github__add_issue_comment`: a readable summary, then exactly one fenced
`json` block, and no other `json` block anywhere in the comment:

```json
[
  {
    "question": "Q1",
    "decisions": ["<every id in Q1's decisions>"],
    "call": "deliberate",
    "note": "<the owner's note, or empty>"
  },
  {
    "question": "Q2",
    "decisions": ["<every id in Q2's decisions>"],
    "call": "fix_source",
    "note": "<the owner's note>",
    "task": "#<the issue step 5 opened>"
  }
]
```

Copy each question's whole `decisions` list. `task` appears only on
`fix_source`. A `domain_owner` answer needs its note. Then tell the owner the
analyst picks it up from the comment's link.
