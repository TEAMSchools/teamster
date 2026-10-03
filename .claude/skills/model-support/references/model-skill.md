# The family skill

Document mode step 7, and the walk test for any skill edit.

## Propose, then ask

From what inventory and intake found, list what a skill for this family would
hold (for a family that already has one, list what to add and what to remove,
then go on to the fact-check below):

- sheet-upkeep procedures the user named at intake (a procedure the doc's
  Process "Steps" already number gets a link to them, not a copy);
- yearly rollover: grep the family SQL for `current_academic_year` and
  hard-coded years or term names;
- QA checks worth re-running after each data load, each reporting what it
  compared (`qa-mode.md` → New data landed);
- questions people keep asking about the numbers;
- before/after measurements that a later QA parity run compares against, dated,
  in the QA reference. Not a changelog: commit messages already carry history.
  Every other count stays in the session scratchpad or the PR body.

For a family that already has a skill, also read its own upkeep instructions
("update this skill", "what to write down") against these rules, and propose
rewording any that conflict. DIBELS told sessions to write down every row count
with its year, so each run added counts that `reference-doc.md` → _What to cut_
then removed.

If the list is empty, say so and propose no skill. Either way, wait for the
user's answer.

## Shape

ICM (Interpretable Context Methodology: a small entry file that only routes, one
reference file per task area, loaded only when a step needs it; the repo's
assessment is issue #5434) inside the repo convention:

- `SKILL.md`: frontmatter `description` that starts "Use when…" and lists
  triggers and model names, never the workflow; the rules that apply to every
  task; a route-by-task table sending each task to one reference; a "why did
  this number change" table if the family has one; the sheet-handoff contract; a
  scripts list. Nothing else.
- `references/*.md`: one file per task area. Always `references/`, never
  `reference/`.
- `scripts/*.py`: helpers the procedures run. Inputs that change every cycle (a
  year's calendar, a roster, a paste, a generated TSV) go in the session
  scratchpad. The repo gets at most a generic `*.example.*` file showing each
  kind of entry once. When a Google Sheet is the record, the skill names it and
  does not copy it: on CARAT, a committed `expected_assessments_2026_27.json`
  duplicated a sheet tab and went stale each year.

Worked example: `.claude/skills/carat-dashboard/` (`SKILL.md`, `references/`,
`scripts/`, and one `*.example.json`).

## Restructuring an oversized skill

1. Measure the skill's `## ` sections:

   ```bash
   awk '/^#{2,4} /{if(h)print n"\t"h; h=$0; n=0} {n++} END{print n"\t"h}' .claude/skills/<name>/SKILL.md
   ```

   Group sections by the task that needs them; sections every task needs go
   together. `###` and deeper headings move with their `## ` parent.

2. Write a mapping JSON: each `## ` heading text → destination file, plus
   `"_default": "SKILL.md"` for lines before the first heading.
3. Split verbatim:

   ```bash
   uv run python <worktree>/.claude/skills/model-support/scripts/split_skill.py <SKILL.md> <mapping.json> <skill dir>
   ```

   It must print equal `lines in` and `lines out`; an unmapped heading stops it
   with the heading's name ([split_skill.py](../scripts/split_skill.py)).

4. Fix cross-file `_Section_` pointers and relative links (`../scripts/`,
   `../../../../docs/`), then run
   `uv run python <worktree>/.claude/skills/model-support/scripts/check_links.py <skill dir>`.
5. Trim the entry file to routing.

## Fact-check the skill

The walk test proves the skill routes; it does not prove the skill is right.
Required when document mode runs on a family that already has a skill. Dispatch
one Opus subagent, edits allowed, to check at least 25 claims in `SKILL.md` and
every reference (model names, columns, joins, filters, partitions, grains)
against the SQL and fix what is wrong. Give it, in the prompt, the list of facts
the doc rewrite cut that the skill lacks (the rewrite agent reports it, with old
line numbers readable through `git show HEAD~1:<doc>`), and have it fix any link
into a doc section that no longer exists. A claim about what a sheet or table
holds (which bands a calendar carries, which years a tab covers) is checked with
a prod query, not the SQL: the DIBELS skill said two grade bands had no `PLIT`
rows when every band in every region had them. On DIBELS the skill still said
grades 6-8 get no BOY goals a week after a commit gave them the EOY goal,
described three models from an unmerged PR as shipped, and told sessions to add
null handling the aimline model already had.

When the skill fact-check runs alongside the doc rewrite, compare the two for
facts they state differently before committing, and settle each with a prod
query. On FRESH the skill called a target question closed and a budget question
settled while the doc listed both as open; prod settled one, and the stakeholder
held the other.

Before any skill text leaves the repo (moved into an issue or PR body, pasted
into a handoff), scan it for student numbers, names, and small cells: a DIBELS
skill section bound for an issue named a student by number, and the same line
was already on `main`.

## Walk test

Required for a new skill and for every edited skill file, on a task that uses
the edit. For a new or restructured skill, write one realistic task per row of
its route table; for an edit, one task that reaches the edited file. Scope each
task to one step of a multi-step mode ("start document mode on X", not "run
document mode on X"): a whole run loads one reference per step by design, so it
fails the limit without telling you anything. Ask the user before dispatching.
One cold Sonnet subagent per task, planning only, with this prompt:

```text
Walk test of a Claude Code skill. Entry file: <abs path>. Read it with the
Read tool, then read only what it routes you to. Do the reading yourself;
no sub-agents. Planning only: no scripts, queries, git, or edits. Task:
<realistic user request>. Return, under 300 words: (1) every file you Read,
in order, with line ranges; (2) your concrete steps; (3) anything unclear,
missing, or mis-pointed.
```

Pass: the entry file plus at most two more files read. Every file counts,
including files in another skill; several `offset` reads of one file count as
one. Fixes that worked on CARAT: merge references that every task needed
together; add an explicit "this overrides step N of X" link; name where a doc
section stops ("read X and Y, stop at heading Z"); link a reference file
directly instead of another skill's entry file. On DDI, every failure was a
reference linking a sibling reference for one fact — inline the one-liner
(cadence, asset names, a table location) instead of pointing; a "full mechanics:
X" parenthetical invites the hop even when the needed facts are already inline.
Re-run until it passes.
