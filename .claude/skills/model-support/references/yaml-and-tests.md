# YAML descriptions, tests, and known issues

Document mode steps 4-6, and update mode for columns, grain changes, and SQL
comments. The SQL is the source of truth over the reference doc and over source
material. `.claude/rules/dbt-yaml.md` loads on the first YAML read; its
description rules (no stats, no TODOs, no issue refs) apply.

## YAML audit

Edit descriptions only. For a new column in update mode, the column entry itself
(`- name:`, `data_type` on a contracted model) is an intentional change; list it
in the commit message.

- About five models or fewer: audit inline.
- More: split the family into groups of about six (staging, intermediate, views)
  and dispatch one Opus subagent per group, all in one message, with this prompt
  (change only the placeholders):

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

A subagent's report is not evidence. Check that only descriptions moved:

```bash
git -C <worktree> diff -U0 -- '*.yml' \
  | rg '^[+-].*(data_type|data_tests|severity|combination_of_columns|contains_pii|materialized|- name:)'
```

Every line this prints must be an intentional change, and each one goes in the
commit message. Then run
`uv run dbt parse --no-partial-parse --project-dir <worktree>/src/dbt/<project>`.

Flags are the audit's most valuable output: a YAML column list that does not
match the SQL, a missing uniqueness test, real duplicates, a wrong grain in a
description. Each flag becomes a test (next section) or a line under "Known
issues, need to fix" in the reference doc.

## Propose tests from the model

For each in-family model, read the grain from the SQL (the `group by`, the
dedupe partition, the join keys) and propose:

- Uniqueness on the grain: `unique` on a single key, or
  `dbt_utils.unique_combination_of_columns`. Required on every staging,
  intermediate, and `rpt_` model (`.claude/rules/dbt-models.md`).
- `not_null` on key columns, never on `generate_surrogate_key` output (it cannot
  return null).
- `accepted_values` on low-cardinality categories: status, region, test type,
  eligibility flags.
- `relationships` to the parent's key where the join is a lookup.

Present a table (model, test, columns, why, prod result) and wait for the user
to approve before adding any test.

## Check against prod first

Through the BigQuery MCP (SELECT-only), rows against distinct keys:

```sql
select
    count(*) as n_rows,
    count(distinct to_json_string(struct(<key columns>))) as n_keys,
from `teamster-332318.<dataset>.<model>`
```

For `accepted_values`, list the distinct values first. Staging tests need
`config: severity: error`; the kipptaf default is warn.

## A test that fails today

Add it anyway; it warns. Put the cause in the reference doc under "Known issues,
need to fix" with the query that shows it, in aggregates only. On CARAT, two
such tests exposed a `strategy_case` fan-out and stored grades matching several
extension rows.

## "Probably harmless" gets a query

Every oddity you suspect is harmless gets checked, not argued:

- An arbitrary `row_number` pick is harmless only if every column the consumers
  read is constant within the partition: `count(distinct <col>)` per partition
  is 1.
- Rows a consumer should never see are harmless only if the consumer's output
  never contains them: group by the consumer's grain and count.

Record each check and its result in the commit message.

## SQL comments

Remove stale counts and "after this PR" narration from SQL comments. Prove the
edit is comment-only:

```bash
git -C <worktree> show origin/main:<path.sql> > <scratchpad>/old.sql
uv run python .claude/skills/model-support/scripts/comment_only_diff.py <scratchpad>/old.sql <worktree>/<path.sql>
```

It prints `comment-only` or `LOGIC CHANGE`
([comment_only_diff.py](../scripts/comment_only_diff.py)). Warn the user that
even a comment edit marks the model `state:modified`, so dbt Cloud CI rebuilds
everything downstream of it.
