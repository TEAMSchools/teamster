# Reference doc

Document mode step 3. Readers: the next owner, and the family skill that links
here. The page is public on GitHub. It lives at
`docs/models/<family>-data-model.md`.

## Outline

Every doc opens with:

1. What it is: one paragraph, who uses it and for what.
2. How it fits together: a diagram from sources to consumers.
3. Terms, including every term the family skill defines: the skill is read by
   Claude, the page by a person. Gradebook audit's skill defined its crosswalk
   tab while the page never mentioned it.
4. Where the data comes from: each source and who owns it. Before naming a
   source, confirm its `ref()` chain reaches the view or process the section
   describes (`rg -o 'ref\("[^"]+"\)'` on each model up the chain). A source
   that feeds a sibling model is not a source of this one: CARAT's docs once
   said College Board SAT files feed the official scores, when official SAT
   reaches CARAT only through kippadb.

The middle depends on the consumer (`intake-and-inventory.md` → Find the
consumers):

- Dashboard: one section per view, each with What it shows / Grain / Reads /
  Worth knowing.
- Process: What triggers it → Inputs → Steps → Outputs (where they land, who
  reads them) → Who runs it and when.

Before writing "live", "today's data" or how a refresh reaches the output, check
the materialization of every model up the chain to the source, in each region's
dataset as well as kipptaf (`<dataset>.__TABLES__`, type 2 is a view), not only
the models the sentence names. A view over tables is only as fresh as those
tables' last build. On Grad Plan the doc said the chain recomputed on read; the
two models it named were views, but the regional models under them were tables,
and the cold review passed it.

The Process "Steps" hold the numbered procedure. The family skill links to them
and keeps only what a person running it needs beyond the doc (timing, checks,
what to do after); it does not repeat the steps.

Every doc closes with:

1. Supporting models, including shared upstreams as one line each and "also read
   by" for in-family models with outside children.
2. Inputs: Google Sheets and other hand-maintained sources.
3. Decisions: why it works the way it does.
4. Known issues, need to fix: each with the query or test that shows it, or, for
   a defect outside the warehouse, where it is tracked. If the doc already has
   an open-questions section, add them there as a subsection instead of a second
   heading.
5. Yearly upkeep.

## What to cut

- One-time before/after measurements. If the family skill cites them, move them
  to a reference there.
- "Resolved —" and "used to" narration, and tombstones.
- Counts that go stale: "27 students" becomes "a few dozen".
- Evidence tables and check dumps.

## Restructuring an oversized doc

When the existing doc runs past about 1,000 lines or is mostly investigation
history rather than a manual (DIBELS was 3,425 lines), dispatch one Opus
subagent to rewrite it into the outline above, with the boundary table, the
owner, and the pending-work links in the prompt. Tell it to check each fact it
cuts against the family skill and list every cut fact the skill lacks, with its
old line number, instead of dropping it. Then route those facts into the skill
(`model-skill.md` → Fact-check the skill). The DIBELS rewrite came to 952 lines
and listed eight such facts and five places the skill contradicted the SQL.

## Public-page rules

- No internal sheet URLs or IDs: write "ask the data team".
- No emails, no student data, no small-cell counts.
- A security defect goes in as shape only: that it exists, what kind, and where
  the fix is tracked. Which page lacks a guard, the exact construct, and which
  instance is reachable go to Asana, never a GitHub issue: this repo and its
  issues are public. After redacting, search for the claim in other words across
  the repo, not only for the removed string: on the PowerSchool plugin, two
  prose passages restated the redacted facts, and one shipped in a distributed
  zip. Redact before the first push: a squash merge keeps the text off `main`,
  but the PR diff, the branch, and commit subjects keep it public.
- No standalone bold line as a heading (markdownlint MD036, `docs/CLAUDE.md`).
- Add the page to the `mkdocs.yml` nav under `Models`.

## Cold review

Required for a new doc and for every edited section. Ask the user before
dispatching; they may skip a trivial edit such as a typo. Dispatch one Opus
subagent with this prompt, changing only the placeholders:

```text
You are reviewing a project manual as the person about to inherit the
project. Read <absolute doc path> in full (or, for an update, only these
sections: <section names>). Then spot-check at least 10 specific factual
claims against the code under <absolute worktree path>/src/dbt.
Prioritise grain, which models read which, join keys and partitions,
filters, and denominators. Do the reading yourself; no sub-agents; no edits.
Then run each query under "Known issues, need to fix" read-only through the
BigQuery MCP against prod datasets, and report whether it runs and its
aggregate result (counts only; any count under 10 as "under 10").
Report: wrong or overstated claims with file:line evidence; where a
newcomer gets lost; what reads like a check dump or change log; anything
inappropriate for a public page; per known-issue query, whether the result
still supports the issue as written.
```

Check each flag against the SQL yourself before editing; the reviewer can be
wrong too. So can your own fix list: tell the fix agent to check each item
against the code before writing it. On FRESH a fix list called the load
partition a file date; it is the export file's school year. Fix every confirmed
flag. On CARAT, a doc its author believed correct had 13; the gradebook audit
and Academic Health pages had six each.

A reviewer's evidence can be older than the owner's last edit. When a flag rests
on a download or a sheet read (a Tableau workbook, a Sheets API pull), check its
time against the owner's edits and re-read a fresh copy before acting. On DIBELS
a reviewer flagged calc branches from a download taken before the owner deleted
them.

Give every known issue its own query before the review. On Academic Health only
three of six had one, and the reviewer had to write checks for the rest.

### Review the YAML and scripts too

The doc review above reads the doc. Before the PR, run the same kind of cold
review over the rest of the diff, in the same dispatch or a second one. On Grad
Plan, `claude-review` was the first to judge the PII tags and the skill's
script, and it found five problems the doc review could not have seen. Add to
the prompt:

```text
Also review the YAML and script changes: `git -C <worktree> diff origin/main...HEAD
-- '*.yml' '*.py'`. For each properties file, read .claude/rules/ferpa-pii.md
and list student-level columns with no column-level contains_pii tag, and
reference-data columns (plan structure, codesets, course attributes) that carry
one. For each script, run it or read it for inputs it assumes (a hard-coded
column, range or ID). For every inconsistency you flag (a model materialized
unlike its siblings, a naming mismatch), check first whether a repo CLAUDE.md or
.claude/rules file says which form is correct, and cite it.
```

## Repoint links

After renaming sections, find pointers to the old names and fix them:

```bash
rg -n '_<Old section name>_|reference doc' .claude/skills
uv run python <worktree>/.claude/skills/model-support/scripts/check_links.py <skill dir> docs/models/<doc>.md
```

The link checker is [check_links.py](../scripts/check_links.py).
