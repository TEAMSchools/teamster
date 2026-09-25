# Reference doc

Document mode step 3. Readers: the next owner, and the family skill that links
here. The page is public on GitHub. It lives at
`docs/models/<family>-data-model.md`.

## Outline

Every doc opens with:

1. What it is: one paragraph, who uses it and for what.
2. How it fits together: a diagram from sources to consumers.
3. Terms.
4. Where the data comes from: each source and who owns it.

The middle depends on the consumer (`intake-and-inventory.md` → Find the
consumers):

- Dashboard: one section per view, each with What it shows / Grain / Reads /
  Worth knowing.
- Process: What triggers it → Inputs → Steps → Outputs (where they land, who
  reads them) → Who runs it and when.

Every doc closes with:

1. Supporting models, including shared upstreams as one line each and "also read
   by" for in-family models with outside children.
2. Inputs: Google Sheets and other hand-maintained sources.
3. Decisions: why it works the way it does.
4. Known issues, need to fix: each with the query or test that shows it.
5. Yearly upkeep.

## What to cut

- One-time before/after measurements. If the family skill cites them, move them
  to a reference there.
- "Resolved —" and "used to" narration, and tombstones.
- Counts that go stale: "27 students" becomes "a few dozen".
- Evidence tables and check dumps.

## Public-page rules

- No internal sheet URLs or IDs: write "ask the data team".
- No emails, no student data, no small-cell counts.
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
Report: wrong or overstated claims with file:line evidence; where a
newcomer gets lost; what reads like a check dump or change log; anything
inappropriate for a public page.
```

Check each flag against the SQL yourself before editing; the reviewer can be
wrong too. Fix every confirmed flag. On CARAT, a doc its author believed correct
had 13.

## Repoint links

After renaming sections, find pointers to the old names and fix them:

```bash
rg -n '_<Old section name>_|reference doc' .claude/skills
uv run python <worktree>/.claude/skills/model-support/scripts/check_links.py <skill dir> docs/models/<doc>.md
```

The link checker is [check_links.py](../scripts/check_links.py).
