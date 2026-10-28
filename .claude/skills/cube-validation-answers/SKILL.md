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
`TEAMSchools/teamster` holds his questions; one comment from him carries his
answers, and the analyst records them. He never edits validation files or runs
the validator, and neither does this session.

## Rules

- Read the questions only from the issue's fenced `json` block, never from its
  markdown.
- Speak in policy words. Name a column, member or file only when he asks.
- His checks are his to run, independent of Claude. Show the steps and the SQL;
  never run the pinned SQL for him.
- **Example students or staff he asks to see come from his own BigQuery access
  and stay in this chat.** Nothing posted carries a student's name, number or
  row, or a staff member's name, email or row: counts and codes only, counts
  under 10 as `<10`.
- Post nothing until he confirms its text.

## Steps

1. Find the issue: the number he gave, else an open issue titled "Validate
   <dashboard> in Cube" for the dashboard he named
   (`mcp__github__search_issues`); if several match, ask which. Read it with
   `mcp__github__issue_read` and parse its one fenced `json` block: a list of
   questions, each with `id`, `reason`, `decisions`, `views`, `definitions`,
   `evidence`, `counts`, `hand_checks`, `moment`, `expires` and `expired`. Read
   its comments too: skip a question an earlier answers comment of his already
   covers, unless he wants to change it, and then send him to the analyst.
2. Say how many questions there are. A question with `expired: true` has pinned
   SQL that no longer runs: he can answer without the checks, or wait for the
   analyst to re-run so they work. When `expires` is within 1 day, tell him when
   his checks stop working, so he runs them first.
3. Ask one question at a time, with everything up front, in this order:
   1. The question in policy words ("Which attendance codes should count as
      tardy?"), built from `reason` and `counts`, with no column names.
   2. Both definitions side by side (`definitions.dashboard` and
      `definitions.cube`), code groups spelled out.
   3. Who differs: the filters on each side, and the rows and students only one
      side counts, by school or grade, from `counts` as given.
   4. What triage found (`evidence`) and why it is his call.
   5. His checks, one per `hand_checks` entry. The dashboard: the filters to set
      (`cut`), the cell to read (`dims`, or the total), and the number to expect
      (`dashboard`) beside Cube's (`cube`). Name the sheet from the comparison's
      `workbook` and `sheet` in `src/cube/validation/<view>.yml` when the
      validation branch is reachable (`mcp__github__get_file_contents`). Then
      each side's SQL (`dashboard_sql`, `cube_sql`) in a fenced `sql` block to
      paste into the BigQuery console, with its dry-run price (`dashboard_usd`,
      `cube_usd`): it is pinned to the run's moment and returns only that cell.
      Tableau shows its last refresh, so a small difference may not match there.
      An entry with `none` has no group cell to show: offer to find an example
      under his access, in this chat.
   6. The choices, with what happens next, plus free text:

      | Choice                     | `call`          | What happens next                                  |
      | -------------------------- | --------------- | -------------------------------------------------- |
      | The dashboard is right     | `fix_cube`      | Cube is fixed under the domain's Cube-fix issue    |
      | Cube is right              | `fix_dashboard` | the domain's Asana dashboard-fix task              |
      | Both fine, intended        | `deliberate`    | recorded; later runs stay quiet on it              |
      | The source data is wrong   | `fix_source`    | a new GitHub issue for that data's owner (step 5)  |
      | Free text ("need to talk") | `domain_owner`  | stays open, with his note in the decision's reason |

4. Answer a follow-up from the same evidence (the question's JSON, the
   validation file, his BigQuery access), say so when it does not answer it,
   then ask the question again with its choices.
5. For "the source data is wrong", draft a GitHub issue for that data's owner in
   the shape of `.github/ISSUE_TEMPLATE/bug_report.md`: the question, both
   definitions, the counts, his note and what his session found, as counts and
   codes, with `Refs #<validation issue>`. Leave out every student and staff
   detail, including ones he looked at here. Ask him whom to assign; the data's
   owner is named only as the GitHub assignee, never in the body. Show him the
   full text and open it with `mcp__github__issue_write` on his confirmation.
   Its `#<number>` is that answer's `task`.
6. At the end, show a summary of his answers: each question, his choice, his
   note. His notes become decision reasons in git, so check each for a student's
   or staff member's name, an email, or an ID or phone number, and ask him to
   reword any (dates and school years are fine). If he stops early, the summary
   covers only what he answered; the rest wait for a later session.
7. On his confirmation, post 1 comment with `mcp__github__add_issue_comment`: a
   readable summary, then exactly one fenced `json` block, and no other `json`
   block anywhere in the comment:

   ```json
   [
     {
       "question": "Q1",
       "decisions": ["<every id in Q1's decisions>"],
       "call": "deliberate",
       "note": "<his note, or empty>"
     },
     {
       "question": "Q2",
       "decisions": ["<every id in Q2's decisions>"],
       "call": "fix_source",
       "note": "<his note>",
       "task": "#<the issue step 5 opened>"
     }
   ]
   ```

   Copy each question's whole `decisions` list. `task` appears only on
   `fix_source`. A `domain_owner` answer needs its note. Then tell him the
   analyst picks it up from the comment's link.
