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
with cwd <worktree>,
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <edited files> </dev/null
and uv run dbt parse --no-partial-parse --project-dir <worktree>/src/dbt/<project>.
Report: per file a one-line summary; FLAGS with file:line evidence (column
lists that don't match the SQL, missing uniqueness tests, wrong grains);
lint and parse results verbatim.
```

A subagent's report is not evidence. Check that only descriptions moved, per
edited file, against main (so staged and committed edits count too):

```bash
git -C <worktree> show origin/main:<path.yml> > <scratchpad>/old.yml
uv run python <worktree>/.claude/skills/model-support/scripts/yaml_description_diff.py <scratchpad>/old.yml <worktree>/<path.yml>
```

It prints `description-only`, or every non-description path that changed (a
dropped test, a trimmed `accepted_values` list, a new column)
([yaml_description_diff.py](../scripts/yaml_description_diff.py)). Every path it
prints must be an intentional change, listed in the commit message. Then run
`uv run dbt parse --no-partial-parse --project-dir <worktree>/src/dbt/<project>`.

Flags are the audit's most valuable output: a YAML column list that does not
match the SQL, a missing uniqueness test, real duplicates, a wrong grain in a
description. Each flag becomes a test (next section) or a line under "Known
issues, need to fix" in the reference doc.

## Propose tests from the model

First list the `data_tests:` already on the model and on its direct parents
(`.claude/rules/dbt-yaml.md` → "Before adding a data-quality test"). A test that
looks missing is often already there upstream at warn; on CARAT, a kippadb
duplicate test said to be missing already existed on
`int_kippadb__standardized_test_unpivot`.

Then, for each in-family model, read the grain from the SQL (the `group by`, the
dedupe partition, the join keys) and propose:

- Uniqueness on the grain: `unique` on a single key, or
  `dbt_utils.unique_combination_of_columns`. Required on every staging,
  intermediate, and `rpt_` model (`.claude/rules/dbt-models.md`), except thin
  district `extracts/` wrappers over a kipptaf view, which carry no tests.
- `not_null` on key columns, never on `generate_surrogate_key` output (it cannot
  return null).
- `accepted_values` on low-cardinality categories: status, region, test type,
  eligibility flags.
- `relationships` to the parent's key where the join is a lookup.
- `dbt_utils.accepted_range` on counts and scores, with the bound set from the
  prod maximum plus headroom. A direction check (a count that should only rise)
  is a different test: on gradebook audit, a 50 typed for a 5 would rise, fill
  the right rows, and pass every check but a bound. Propose both.

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
need to fix" with the query that shows it, in aggregates only.

Count duplicates on the source-grain model with its full natural key, including
every column that legitimately repeats within a day (subject, section,
administration); give an unpivoted count only as a labelled second number. On
CARAT, grouping `int_kippadb__standardized_test_unpivot` on contact, score type
and date dropped the AP subject, so students who sat several AP exams in one day
read as over a thousand duplicate groups; `stg_kippadb__standardized_test` on
contact, date, test type and subject has none, and PSAT fell to a third (three
score types per sitting). A cleanup list built from the unpivoted count would
have deleted real results. The worked example is "Hunting duplicates in kippadb"
in `.claude/skills/carat-dashboard/references/goals.md` (on the branch of PR
#5542 until it merges). On CARAT, two such tests exposed a `strategy_case`
fan-out and stored grades matching several extension rows.

## "Probably harmless" gets a query

Every oddity you suspect is harmless gets checked, not argued:

- An arbitrary `row_number` pick is harmless only if every column the consumers
  read is constant within the partition: `count(distinct <col>)` per partition
  is 1.
- Rows a consumer should never see are harmless only if the consumer's output
  never contains them: group by the consumer's grain and count.

Record each check and its result in the commit message, as aggregates without
small cells (`.claude/rules/ferpa-pii.md`); git history is permanent.

## Tiered matches

When a model matches records in tiers (exact ID, then name and birth date, and
so on), check both of these; three CARAT and state-testing match queries have
shipped with one or the other:

- Tier conditions compare normalized values, not raw strings. Exact string
  equality misses case, whitespace, and leading zeros. Count the records that
  match only after `lower(trim(...))` or the ID's zero-padding on both sides.
- A record with more than one candidate at a tier comes out labeled ambiguous,
  never falling through to "no match". Count candidates per source record per
  tier; any count above 1 must reach the ambiguous label.

## Status ladders

When a column is a `case` that assigns a status or tier and stops at the first
match, check two things against prod before documenting it:

- Rows whose inputs are all present but whose status is null. Each one is a
  missing branch (athletic eligibility had 43).
- Rows that match a branch meant for another group. A branch for one grade band
  written as `grade_level >= 6` also catches every older student, so a later
  branch never fires. List the branch order and the range each branch covers.

## SQL comments

Remove stale counts and "after this PR" narration from SQL comments. Prove the
edit is comment-only:

```bash
git -C <worktree> show origin/main:<path.sql> > <scratchpad>/old.sql
uv run python <worktree>/.claude/skills/model-support/scripts/comment_only_diff.py <scratchpad>/old.sql <worktree>/<path.sql>
```

It prints `comment-only` or `LOGIC CHANGE`
([comment_only_diff.py](../scripts/comment_only_diff.py)). Warn the user that
even a comment edit marks the model `state:modified`, so dbt Cloud CI rebuilds
everything downstream of it.
