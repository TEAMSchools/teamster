# The family skill

Document mode step 7, and the walk test for any skill edit.

## Propose, then ask

From what inventory and intake found, list what a skill for this family would
hold:

- sheet-upkeep procedures the user named at intake;
- yearly rollover: grep the family SQL for `current_academic_year` and
  hard-coded years or term names;
- QA checks worth re-running after each data load;
- questions people keep asking about the numbers;
- before/after measurements the reference doc no longer carries.

If the list is empty, say so and propose no skill. Either way, wait for the
user's answer.

## Shape

ICM inside the repo convention:

- `SKILL.md`: frontmatter `description` that starts "Use when…" and lists
  triggers and model names, never the workflow; the rules that apply to every
  task; a route-by-task table sending each task to one reference; a "why did
  this number change" table if the family has one; the sheet-handoff contract; a
  scripts list. Nothing else.
- `references/*.md`: one file per task area. Always `references/`, never
  `reference/`.
- `scripts/*.py`: helpers the procedures run.

Worked example: `.claude/skills/tableau-workbook-xml/`.

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
   uv run python .claude/skills/model-support/scripts/split_skill.py <SKILL.md> <mapping.json> <skill dir>
   ```

   It must print equal `lines in` and `lines out`; an unmapped heading stops it
   with the heading's name ([split_skill.py](../scripts/split_skill.py)).

4. Fix cross-file `_Section_` pointers and relative links (`../scripts/`,
   `../../../../docs/`), then run
   `uv run python .claude/skills/model-support/scripts/check_links.py <skill dir>`.
5. Trim the entry file to routing.

## Walk test

Required for a new skill and for every edited skill file, on a task that uses
the edit. For a new or restructured skill, write one realistic task per row of
its route table; for an edit, one task that reaches the edited file. Ask the
user before dispatching. One cold Sonnet subagent per task, planning only, with
this prompt:

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
directly instead of another skill's entry file. Re-run until it passes.
