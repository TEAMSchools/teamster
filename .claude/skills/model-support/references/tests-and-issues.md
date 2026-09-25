# Tests and known issues

Document mode steps 5-6, and update mode for columns and grain changes.

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
