---
name: model-support
description: >-
  Use when documenting a dbt model family for handover (a Tableau dashboard's
  lineage, or a process model such as a Google Sheet extract), updating a
  documented family's reference doc, YAML descriptions, tests, or skill after a
  model change, or QA-ing prod values after new data lands or after a refactor
  that should not change them. Triggers: "document this model", "update the docs
  for", "write a reference doc", "restructure this skill", "check prod values",
  "did the refactor change anything", "new scores landed", or a docs/models page
  or family skill that no longer matches the SQL.
---

# Model support

Three modes for one dbt model family: document, update, QA. Pick the mode from
the request; if it is unclear, ask.

## Rules for every mode

- No Tableau MCP call and no `tableau-workbook-xml` load without telling the
  user it costs a lot of tokens and getting a yes. QA goes to the warehouse
  first.
- Sheet changes go out as the whole tab or block, as a tab-separated file,
  handed over with the sheet link and tab name. Never comma-separated; never
  pasted into chat. In VS Code a link to the session scratchpad (`/tmp`) does
  not open, so put the file in the gitignored `.claude/scratch/` under a
  distinctive name, and delete it once the owner has pasted.
- Before building a whole-tab replacement, diff the live tab (a CSV the owner
  exports) against the model on the tab's key, and list for the owner every cell
  outside the intended change, with the tab row and column. The tab can be an
  older snapshot or carry deliberate edits; the owner decides which wins. Also
  match the tab's column order (ask for a screenshot of its header) and its
  number format: a rounded `numeric` column prints as `2.000000000`.
- Read the source the user is editing (a Sheets external through ADC from
  Python), not a reshaped staging table.
- State how a pipeline behaves only from code or a before/after observation,
  never from a timestamp.
- Read the whole block before flagging a bug in it.
- No doc claim ships without the cold review; no skill edit ships without a walk
  test. Ask before each dispatch; the user may skip one for a trivial edit.
- Student-level rows stay in the terminal and the session scratchpad. Commit
  messages, PRs, docs and skill files get aggregates without small cells; a
  yearly count of 2 early graduates is a small cell.
- When the user says a column or rule works differently from what the SQL shows,
  search merged PRs for the model and column names before answering, and cite
  the line and the PR once. Then ask one yes-or-no question about changing the
  code; do not re-argue it in later messages.
- Status updates and the final report come in three groups: done, pending (your
  work), and needs their decision. Lead with a one-line result. Nothing else.
- A count taken from an issue, PR, skill, or doc gets re-run before it goes into
  new writing, and the new writing says when it was measured (the root CLAUDE.md
  "re-run its diagnostic" rule, applied to every number). A month-old AP count
  copied without re-running reached a manual, a skill, two issues, a handoff
  doc, and Asana, and was wrong.
- When a finding is corrected, fix every body it appears in, not just a comment:
  the issue and PR bodies (with a dated correction line), the published doc, and
  the skill. Then `rg` the repo and search the tracker for the old number so no
  copy survives.
- Check a claim about a model, yml or doc against `origin/main`
  (`git show origin/main:<path>` or a fresh worktree), not the main checkout,
  which lags. A "stale description" finding read off the main checkout had
  already been fixed on main.
- Done means the owner said it is done. Green CI and a ready-to-merge review
  make a PR ready to ask about; they do not finish the project. Ask before
  marking a project Done, reassigning its tracker task, or telling anyone it is
  ready.
- When the owner's screen and the repo disagree on a name (a PowerSchool button,
  a Tableau field), the screen wins: fix the description to match. A cold review
  that flags the owner's wording against an older yml has it backwards.
- Relative paths in commands (`docs/models`, `.claude/skills`) mean the checkout
  being edited. In a worktree, run them with `cd <worktree> &&` in the same
  command; from the main checkout they read stale copies and report a false
  clean.

## Route by step

| Mode     | Step                                        | Read                                                          |
| -------- | ------------------------------------------- | ------------------------------------------------------------- |
| Document | 1-2 Intake, consumers, boundary, inventory  | [intake-and-inventory.md](references/intake-and-inventory.md) |
| Document | 3 Reference doc and cold review             | [reference-doc.md](references/reference-doc.md)               |
| Document | 4-6 YAML, tests, known issues, SQL comments | [yaml-and-tests.md](references/yaml-and-tests.md)             |
| Document | 7 Family skill, fact-check, walk test       | [model-skill.md](references/model-skill.md)                   |
| QA       | New data landed, or refactor parity         | [qa-mode.md](references/qa-mode.md)                           |

Document mode runs steps 1-8 in order, reading each step's file when it starts.
Step 1 asks the user for source material and sheet-upkeep processes before any
SQL is read. Step 2 ends only when the user confirms the family boundary.

## Update mode

For a change to a family that already has a reference doc. With no doc, or for a
refresh with no change behind it (a handover, a doc that has drifted), run
document mode; its intake reads the existing doc and skill first. Find the doc
and family skill with `rg -l '<changed model>' docs/models .claude/skills`. Find
what moved with
`git -C <worktree> diff origin/main...HEAD -- <family .sql and .yml paths>`,
read each hunk in full, then route by the kind of change:

| Change                           | Read                                                                              | Then                                                                                                                      |
| -------------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| New or renamed column            | [yaml-and-tests.md](references/yaml-and-tests.md), `reference-doc.md`             | Update the doc sections and family-skill files that name the column                                                       |
| Join, filter, or grain change    | [yaml-and-tests.md](references/yaml-and-tests.md), `qa-mode.md`                   | Prod grain check, refactor parity if values may move, then fix every doc section and known issue that states the old rule |
| Logic in a status or tier `case` | [yaml-and-tests.md](references/yaml-and-tests.md) → Status ladders, `qa-mode.md`  | Ladder checks, then refactor parity by transition                                                                         |
| New view, sheet tab, or model    | [intake-and-inventory.md](references/intake-and-inventory.md), `reference-doc.md` | Boundary check, a new doc section, a new route in the family skill                                                        |
| SQL comment only                 | [yaml-and-tests.md](references/yaml-and-tests.md) → SQL comments                  | Comment-only proof and the CI warning                                                                                     |
| New known issue, no diff         | [reference-doc.md](references/reference-doc.md) → Outline, Public-page rules      | Add it under known issues; security specifics go to Asana                                                                 |

A rename sweep includes `*.md`: `rg -n '<old name>' --glob '*.{sql,yml,md}'`.
For a name written in prose, also sweep a loose pattern of its key words
(`rg -n -i 'graduation.?progress'`): the exact string missed a second copy
spelled `GraduationProgress`. Every edited doc section then gets the cold
review, and every edited family-skill file a walk test (rules above).

## Step 8: close out

Run trunk on every changed file, with cwd in the edited checkout
(`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`),
and
`uv run dbt parse --no-partial-parse --project-dir <worktree>/src/dbt/<project>`.
A fresh worktree has no `dbt_packages/`, so run
`uv run dbt deps --project-dir <worktree>/src/dbt/<project>` first, in its own
Bash call. Commit with messages that state what was verified, push, and open the
PR. Before asking for review, rewrite the PR body's Summary from
`git diff --stat origin/main...HEAD` and the commit list, so it describes the
whole PR and not its first commit, and check every CI checkbox claim against
`gh pr checks <n>`. Tell the user every judgment call they might disagree with.
Where this skill's steps were wrong or missing for the family, propose the edit
to this skill in the report.

## Scripts

- [split_skill.py](scripts/split_skill.py): verbatim split of an oversized
  skill, lines in = lines out.
- [check_links.py](scripts/check_links.py): relative links that do not resolve.
- [comment_only_diff.py](scripts/comment_only_diff.py): prove a SQL edit is
  comment-only.
- [yaml_description_diff.py](scripts/yaml_description_diff.py): prove a YAML
  edit changed descriptions only.
- [tableau_unused_calcs.py](scripts/tableau_unused_calcs.py): a workbook's
  unused calculated fields, in a safe delete order (`qa-mode.md` → Unused
  workbook fields).

## Acceptance for a run

- Walk tests pass: the entry file plus at most two more reads.
- The cold review finds no wrong claims after fixes.
- The YAML diff is description-only, apart from listed intentional changes.
- `dbt parse` and trunk pass.
- Every missing uniqueness test is added or listed as a known issue.
