# YAML audit

Document mode step 4, and update mode for a new or renamed column. Edit
descriptions only. The SQL is the source of truth over the reference doc and
over source material. `.claude/rules/dbt-yaml.md` loads on the first YAML read;
its description rules (no stats, no TODOs, no issue refs) apply.

## Sizing

- About five models or fewer: audit inline.
- More: split the family into groups of about six (staging, intermediate, views)
  and dispatch one Opus subagent per group, all in one message.

## The audit prompt

Change only the placeholders:

```text
Audit dbt YAML descriptions against the SQL for these models: <list, each
with its absolute .sql and properties .yml path under <worktree>>. Do the
edits yourself; no sub-agents. Edit descriptions only: never SQL, tests,
config, contains_pii, contract, data_type, or column names. The SQL is the
source of truth over any doc. Never change a test to match a description
or the reverse: flag the disagreement instead. Remove change-log narration,
stale counts, TODOs, and issue refs (#1234) from descriptions. Then run,
from <worktree>, trunk check --force --no-fix on each edited file and
uv run dbt parse --no-partial-parse --project-dir <worktree>/src/dbt/<project>.
Report: per file a one-line summary; FLAGS with file:line evidence (column
lists that don't match the SQL, missing uniqueness tests, wrong grains);
lint and parse results verbatim.
```

## Verify the diff yourself

A subagent's report is not evidence. Check that only descriptions moved:

```bash
git -C <worktree> diff -U0 -- '*.yml' \
  | rg '^[+-].*(data_type|data_tests|severity|combination_of_columns|contains_pii|materialized|- name:)'
```

Every line this prints must be an intentional change, and each one goes in the
commit message. Then run
`uv run dbt parse --no-partial-parse --project-dir <worktree>/src/dbt/<project>`.

## Flags

Flags are the audit's most valuable output: a YAML column list that does not
match the SQL, a missing uniqueness test, real duplicates, a wrong grain in a
description. Each flag becomes a test (`tests-and-issues.md`) or a line under
"Known issues, need to fix" in the reference doc.
