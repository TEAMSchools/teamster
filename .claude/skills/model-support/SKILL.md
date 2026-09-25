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
- Sheet changes go out as the whole tab or block, as a tab-separated file in the
  session scratchpad, handed over as a path with the sheet link and tab name.
  Never comma-separated; never pasted into chat.
- Read the source the user is editing (a Sheets external through ADC from
  Python), not a reshaped staging table.
- State how a pipeline behaves only from code or a before/after observation,
  never from a timestamp.
- Read the whole block before flagging a bug in it.
- No doc claim ships without the cold review; no skill edit ships without a walk
  test. Ask before each dispatch.
- Student-level rows stay in the terminal and the session scratchpad.

## Route by step

| Mode     | Step                                        | Read                                                          |
| -------- | ------------------------------------------- | ------------------------------------------------------------- |
| Document | 1-2 Intake, consumers, boundary             | [intake-and-inventory.md](references/intake-and-inventory.md) |
| Document | 3 Reference doc and cold review             | [reference-doc.md](references/reference-doc.md)               |
| Document | 4-6 YAML, tests, known issues, SQL comments | [yaml-and-tests.md](references/yaml-and-tests.md)             |
| Document | 7 Family skill, restructure, walk test      | [model-skill.md](references/model-skill.md)                   |
| QA       | New data landed, or refactor parity         | [qa-mode.md](references/qa-mode.md)                           |

Document mode runs steps 1-8 in order, reading each step's file when it starts.
Step 1 asks the user for source material and sheet-upkeep processes before any
SQL is read. Step 2 ends only when the user confirms the family boundary.

## Update mode

For a change to a family that already has a reference doc (none: run document
mode). Find the doc and family skill with
`rg -l '<changed model>' docs/models .claude/skills`. Find what moved with
`git -C <worktree> diff origin/main...HEAD -- <family .sql and .yml paths>`,
read each hunk in full, then route by the kind of change:

| Change                        | Read                                                                              | Then                                                                |
| ----------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| New or renamed column         | [yaml-and-tests.md](references/yaml-and-tests.md), `reference-doc.md`             | Update the doc sections and family-skill files that name the column |
| Join, filter, or grain change | [yaml-and-tests.md](references/yaml-and-tests.md), `qa-mode.md`                   | Prod grain check, then refactor parity if values may move           |
| New view, sheet tab, or model | [intake-and-inventory.md](references/intake-and-inventory.md), `reference-doc.md` | Boundary check, a new doc section, a new route in the family skill  |
| SQL comment only              | [yaml-and-tests.md](references/yaml-and-tests.md) → SQL comments                  | Comment-only proof and the CI warning                               |

A rename sweep includes `*.md`: `rg -n '<old name>' --glob '*.{sql,yml,md}'`.
Every edited doc section then gets the cold review, and every edited
family-skill file a walk test (rules above).

## Step 8: close out

Run trunk on every changed file
(`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`)
and
`uv run dbt parse --no-partial-parse --project-dir <worktree>/src/dbt/<project>`.
Commit with messages that state what was verified, push, and open the PR. Tell
the user every judgment call they might disagree with.

## Scripts

- [split_skill.py](scripts/split_skill.py): verbatim split of an oversized
  skill, lines in = lines out.
- [check_links.py](scripts/check_links.py): relative links that do not resolve.
- [comment_only_diff.py](scripts/comment_only_diff.py): prove a SQL edit is
  comment-only.

## Acceptance for a run

- Walk tests pass: the entry file plus at most two more reads.
- The cold review finds no wrong claims after fixes.
- The YAML diff is description-only, apart from listed intentional changes.
- `dbt parse` and trunk pass.
- Every missing uniqueness test is added or listed as a known issue.
