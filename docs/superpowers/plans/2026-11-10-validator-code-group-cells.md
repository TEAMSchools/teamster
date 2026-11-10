# Validator code-group cells Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the Cube validator size and prove count cells that differ because
a Tableau code group and a Cube flag count codes differently, and give the owner
a per-code question with a usage profile.

**Architecture:** A comparison declares its code groups as structured lists; the
loader expands each into a `dashboard_columns` entry. A comparison also declares
`aggregate: sum`, which makes `_rebuilt` rebuild cells as sums. `triage` runs 1
priced aggregate query per code group over Cube's daily fact and caches a
per-code usage profile in `triage.json`. `review` groups the code-group causes
into 1 question per code group, with a `codes` map from each code to its
decision ids, so the owner answers per code.

**Tech Stack:** Python 3.13, sqlglot, DuckDB-backed fakes in tests, BigQuery.

**Spec:**
`docs/superpowers/specs/2026-11-10-validator-code-group-cells-design.md`

**Planning decision to check (not in the spec):** the spec asks for "1 question
per measure" and also "a code shared by 2 comparisons (tardy and on-time) gets 1
call". Tardy and on-time are different measures, so this plan groups questions
by **code group** (Tardy, Absent, OSS): % On-Time folds into the Tardy question,
and each code is answered once.

## Global Constraints

- No student value reaches GitHub: posted counts under 10 show as `<10`
  (`report.MASK_BELOW = 10`, `report.mask`); school names may show.
- `RowSpec.values` stays plain column pairs; the only SQL in YAML stays in
  `dashboard_columns`. Code-group codes are data, never SQL.
- The tool posts nothing itself. Every paid query runs inside
  `wh.budget(max_usd)` and the daily cap.
- A row a proof does not name falls to `UNEXPLAINED`; no change to that rule.
- Tests: `uv run --with duckdb pytest tests/scripts/cube_validation/<file> -q`
  from the worktree root. Never bare `uv run pytest`.
- Commits: conventional commits, `Refs #6212`, ending with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Stage files by
  name.

## Review Focus

1. A Cube side with no rows in a cell (Miami, no tardy data) must rebuild to
   blank (`None`), not `0`, in sum mode; the dashboard's `0` then differs.
   Pinned in Task 2.
2. A code containing a quote, space, or SQL must be refused at load, since codes
   are interpolated into SQL. Pinned in Task 1.
3. Every existing mean-mode comparison (ADA, % On-Time) must size exactly as
   before. Pinned in Task 2.
4. A profile count under 10 must be masked in the posted JSON and the issue
   body, while the school name shows. Pinned in Task 4.
5. A profile query over the cost cap must leave triage running and the question
   saying the profile is unavailable, not crash. Pinned in Task 3.

---

## File structure

- `scripts/cube_validation/config.py`: `CodeGroup`, `Comparison.code_groups`,
  `Comparison.aggregate`, `TASK_KEYS` gains `dashboard`.
- `scripts/cube_validation/codes.py` (new): code-group logic with no I/O:
  `profile_sql`, `profiles_from`, `code_of`.
- `scripts/cube_validation/confirm.py`: sum mode in `_rebuilt` and its messages.
- `scripts/cube_validation/triage.py`: run the profile query, cache
  `code_profiles`.
- `scripts/cube_validation/report.py` and `answers.py`: the code-group question,
  its `codes` map and profile.
- `.claude/skills/cube-validation/SKILL.md`,
  `.claude/skills/cube-validation-answers/SKILL.md`: runbook changes.

### Task 1: Config: code groups, aggregate, and the dashboard task

**Files:**

- Modify: `scripts/cube_validation/config.py` (`TASK_KEYS` line 29; the
  `CALLS_NEEDING_TASK` comment lines 23-25; `Comparison` after line 170;
  `_comparison` parse near 389-394 and constructor 396-425)
- Test: `tests/scripts/cube_validation/test_config.py`

**Interfaces:**

- Produces:
  - `@dataclass(frozen=True) class CodeGroup: column: str; codes: tuple[str, ...]; fact_code: str; fact_flag: str`
  - `Comparison.code_groups: dict[str, CodeGroup]` (default `{}`)
  - `Comparison.aggregate: str` (default `"mean"`), one of
    `AGGREGATES = ("mean", "sum")`
  - `TASK_KEYS = ("cube_fix", "dashboard_fix", "dashboard")`
  - At load, each code group `name` adds
    `dashboard_columns[name] = "IF(<column> IN ('<c1>', '<c2>'), 1, 0)"` (codes
    in the YAML's order). A name already in `dashboard_columns` is refused.

YAML shape:

```yaml
code_groups:
  tardy_group:
    column: att_code
    codes: [ET, T, T10, TLE]
    fact_code: attendance_code
    fact_flag: is_tardy
aggregate: sum
```

- [ ] **Step 1: Write the failing tests** in `test_config.py`, using `_write`
      (line 67) and `EXAMPLE` (line 15):
  - `test_code_group_expands_into_a_dashboard_column`: loading the YAML above
    gives
    `code_groups["tardy_group"] == CodeGroup("att_code", ("ET", "T", "T10", "TLE"), "attendance_code", "is_tardy")`
    and
    `dashboard_columns["tardy_group"] == "IF(att_code IN ('ET', 'T', 'T10', 'TLE'), 1, 0)"`.
  - `test_code_group_refuses_a_code_that_is_not_plain` (parametrize `"T'"`,
    `"T T"`, `"T);--"`, `""`): raises the loader's error naming the code.
  - `test_code_group_refuses_non_identifier_columns`: `column: "att code"` and
    `fact_flag: "is-tardy"` each refused.
  - `test_code_group_name_clashing_with_dashboard_columns_is_refused`.
  - `test_aggregate_defaults_to_mean_and_refuses_others`: absent → `"mean"`;
    `aggregate: median` refused naming `mean, sum`.
  - `test_tasks_accept_a_dashboard_key`:
    `tasks: {dashboard: "https://app.asana.com/0/1/2"}` loads.
- [ ] **Step 2: Run**
      `uv run --with duckdb pytest tests/scripts/cube_validation/test_config.py -q`.
      Expected: the 6 new tests FAIL.
- [ ] **Step 3: Implement** in `config.py`: `CodeGroup`, `AGGREGATES`,
      `_CODE = re.compile(r"[A-Za-z0-9_-]+")`,
      `_code_groups(reader) ->     dict[str, CodeGroup]` (identifiers through
      `_IDENTIFIER`, codes through `_CODE`, non-empty list), and the merge into
      `dashboard_columns`. Reword the `CALLS_NEEDING_TASK` comment: a
      `fix_source` task is the Asana task for the source owner.
- [ ] **Step 4: Run** the same command. Expected: all PASS.
- [ ] **Step 5: Commit**
      `feat(cube): declare code groups and a sum aggregate on a comparison`.

### Task 2: Sum mode in cell sizing

**Files:**

- Modify: `scripts/cube_validation/confirm.py` (`_rebuilt` 1305-1330;
  `link_cells` docstring 1361-1366, message 1447, summary 1491-1494)
- Test: `tests/scripts/cube_validation/test_confirm.py`

**Interfaces:**

- Consumes: `Comparison.aggregate` (Task 1).
- Produces: `_rebuilt(spec, entries, cell) -> tuple` returns per side `total`
  when `spec.aggregate == "sum"`, `total / n` when `"mean"`, and `None` when
  `n == 0` in both modes.

- [ ] **Step 1: Write the failing tests**, building on `_side` (1304), `_entry`
      (1308), `_rate_run` (1321) and `RATE` (1294) with
      `dataclasses.replace(RATE, aggregate="sum", decimals=0)` as `SUM_RATE`:
  - `test_sum_mode_rebuilds_a_cell_as_the_sum`: entries `match` (c sum 5, d
    sum 5) and `value_differs` (c sum 2, d sum 0) → `_rebuilt` returns
    `(7.0, 5.0)`, and `link_cells` links the cell when the run's values are Cube
    `7`, dashboard `5`.
  - `test_sum_mode_keeps_a_side_with_no_rows_blank`: Cube side `n = 0`,
    dashboard sum `0` over 3 rows → `(None, 0.0)`.
  - `test_mean_mode_is_unchanged`: the existing rate fixture with `aggregate`
    left default rebuilds to the same values as before this change (assert the
    means the current rate tests assert).
  - `test_sum_mode_summary_says_sum`: the unsized-cell summary text contains
    `sum of the value column`, and the mean one still says `mean`.
- [ ] **Step 2: Run**
      `uv run --with duckdb pytest tests/scripts/cube_validation/test_confirm.py -q`.
      Expected: the new tests FAIL; existing ones PASS.
- [ ] **Step 3: Implement** the branch at the `out.append(...)` line in
      `_rebuilt` and the 3 message strings in `link_cells`.
- [ ] **Step 4: Run** the same command. Expected: all PASS.
- [ ] **Step 5: Commit**
      `feat(cube): size sum-measure cells by summing each side`.

### Task 3: Usage profile in triage

**Files:**

- Create: `scripts/cube_validation/codes.py`
- Modify: `scripts/cube_validation/triage.py` (`run_triage` budget block
  1203-1252; saved dict 1257-1269)
- Test: `tests/scripts/cube_validation/test_codes.py` (new),
  `tests/scripts/cube_validation/test_triage.py`

**Interfaces:**

- Consumes: `CodeGroup`, `ViewConfig.fact` (Task 1);
  `pipeline._as_of(sql, ts, wh)`, `wh.rows`, `CostCapError`.
- Produces:
  - `codes.profile_sql(fact: str, group: CodeGroup) -> str`: 1 aggregate query
    over `` `teamster-332318`.`<dataset>`.`<table>` `` (from `fact`), left
    joined to `` `teamster-332318`.`kipptaf_marts`.`dim_locations` `` on
    `location_key` and `dim_regions` on `region_key`, where
    `<fact_code> IS NOT NULL`, returning
    `code, academic_year, school (abbreviation), region (name), n_days, cube_weight`
    where `cube_weight = AVG(CAST(<fact_flag> AS FLOAT64))`, grouped by the
    first 4.
  - `codes.profiles_from(rows: list[dict], group: CodeGroup) -> list[dict]`: 1
    entry per code where Cube's rule and the dashboard's disagree, sorted by
    code:
    `{"code", "dashboard": 0|1, "cube_weight": float, "years": [{"academic_year", "n_days", "share"}], "schools": [{"school", "region", "n_days"}]}`.
    A code disagrees when `round(cube_weight, 2)` differs from `1` (code in
    `group.codes`) or `0`. `share` is the code's days over all coded days that
    year.
  - `codes.code_of(label: str) -> str | None`: the code in a cause label of the
    form `code <CODE>: <words>`, else `None`.
  - `triage.json` gains
    `code_profiles: {comparison_id: {group_name: list | {"unavailable": str}}}`.

- [ ] **Step 1: Write the failing tests** in `test_codes.py`:
  - `test_profile_sql_is_one_aggregate_over_the_fact`: parses with sqlglot, has
    no `*`, groups by the 4 columns, reads the fact with each part in its own
    backticks, and passes `confirm.check_reproduce(sql, grain=set())`.
  - `test_profiles_from_keeps_only_disagreeing_codes`: rows for `T` (weight 1,
    in group), `TD` (weight 1, not in group), `ET` (weight 0, in group), `A`
    (weight 0, not in group) → codes `["ET", "TD"]`.
  - `test_profiles_from_reports_years_and_schools`: `TD` in 2 years and 2
    schools gives both years with `share` = its days over that year's coded
    days, and both schools.
  - `test_code_of_reads_the_label_convention`:
    `"code TD: counts in Cube, not on the dashboard"` → `"TD"`;
    `"sheet filter Enroll Status"` → `None`. In `test_triage.py`, using `_Wh`
    (458) and `_write_run_triage` (829):
  - `test_triage_caches_code_profiles`: a config with 1 code group writes
    `code_profiles[<comparison>]["tardy_group"]` to `triage.json`.
  - `test_triage_records_an_unavailable_profile_over_the_cap`: `wh.rows` raises
    `CostCapError` → triage exits 0 and the entry is
    `{"unavailable": "<the cap message>"}`.
- [ ] **Step 2: Run**
      `uv run --with duckdb pytest tests/scripts/cube_validation/test_codes.py tests/scripts/cube_validation/test_triage.py -q`.
      Expected: new tests FAIL.
- [ ] **Step 3: Implement** `codes.py`, then in `run_triage`, inside the
      existing `wh.budget` block, 1 query per code group per comparison through
      `pipeline._as_of(..., moment.start, wh)` and `wh.rows`, catching
      `CostCapError` per group (pattern: `value_check` 996 and its `values()`
      closure 1194-1198). Save the result under `code_profiles`.
- [ ] **Step 4: Run** the same command. Expected: all PASS.
- [ ] **Step 5: Commit**
      `feat(cube): profile each disagreeing code's use across years and schools`.

### Task 4: The code-group owner question

**Files:**

- Modify: `scripts/cube_validation/report.py` (`_questions` key at 685;
  `render_review_issue` 969-1076), `scripts/cube_validation/answers.py`
  (question dict 783-801)
- Test: `tests/scripts/cube_validation/test_report.py`,
  `tests/scripts/cube_validation/test_answers.py`

**Interfaces:**

- Consumes: `codes.code_of`, `triage.json` `code_profiles` (Task 3),
  `Comparison.code_groups` (Task 1).
- Produces:
  - In `_questions`, a cause decision whose `code_of(label)` is a code and whose
    groups' comparisons share a code group name is keyed
    `("code_group", group_name, d.task)`. Its question dict gains
    `codes: {code: [decision ids]}` and `group: group_name`. Every other cause
    keeps today's key.
  - The posted question JSON gains `codes` (that map) and `profiles`
    (`{code: profile}` from `code_profiles`, with `n_days` passed through
    `report.mask`, `share` rounded to 3 places, schools kept by name).
  - The issue body renders, per code-group question: each side's rule from
    `definitions`, then per code: dashboard 0/1, Cube weight, a years line, and
    a schools line, all counts masked.
  - The question's `reproduce.queries` gains
    `{"bucket": "profile", "sql": codes.profile_sql(cfg.fact, group)}`, so the
    owner can re-run the profile on today's data.

- [ ] **Step 1: Write the failing tests**:
  - `test_report.py::test_code_causes_merge_into_one_question_per_group`: 2
    comparisons sharing `tardy_group`, causes `code TD: ...` and `code TE: ...`
    on both → 1 question, `codes == {"TD": [ids], "TE": [ids]}` with both
    comparisons' decision ids under each code.
  - `test_report.py::test_other_causes_keep_their_own_question`: a
    `sheet filter Enroll Status` cause beside them stays its own question.
  - `test_report.py::test_code_profile_counts_are_masked_in_the_body`: a school
    with 4 days shows its name and `<10`; a year with 250 days shows `250`.
  - `test_answers.py::test_questions_json_carries_codes_and_masked_profiles`:
    the posted question has `codes` and `profiles`, and no `n_days` under 10
    appears as a number.
  - `test_answers.py::test_code_group_question_reproduces_the_profile`: the
    question's `reproduce.queries` holds an entry with `bucket == "profile"`
    whose `sql` equals `codes.profile_sql(cfg.fact, group)`.
  - `test_answers.py::test_per_code_answers_record_separately`: 2 answers to the
    same question (`TD` `deliberate`, `TE` `fix_source` with an
    `https://app.asana.com/...` task) produce 2 `Change`s with those calls,
    through `parse_answers` and `answer_changes`.
- [ ] **Step 2: Run**
      `uv run --with duckdb pytest tests/scripts/cube_validation/test_report.py tests/scripts/cube_validation/test_answers.py -q`.
      Expected: the new tests FAIL (the per-code answer test may already pass;
      keep it as the record of the format).
- [ ] **Step 3: Implement** the key, the `codes` map, the `profiles` block, and
      the body lines. The profile block counts toward the body cap like the
      Reproduce block and moves to a comment the same way.
- [ ] **Step 4: Run** the same command. Expected: all PASS.
- [ ] **Step 5: Commit**
      `feat(cube): ask the owner once per code group, with a call per code`.

### Task 5: Runbooks

**Files:**

- Modify: `.claude/skills/cube-validation/SKILL.md` (step 3 optional keys
  138-181; step 8 known issue 442-444; step 9 calls 463-465; `tasks:` block
  494-497), `.claude/skills/cube-validation-answers/SKILL.md` (step 1 keys
  42-44; answer table line 98; step 5 104-112; example 125-141; rule 143-145)

**Interfaces:**

- Consumes: every key and format from Tasks 1-4.

- [ ] **Step 1: Edit `cube-validation`:**
  - Step 3: document `code_groups` (copy codes from `discover`'s
    `[Name: Group = c1, c2]` suffix), `aggregate: sum` for a measure that adds
    up, and `dashboard_columns`.
  - Steps 8 and 9: a code-group cause label is `code <CODE>: <words>`; a
    `fix_source` task is an Asana subtask of the dashboard's Asana task
    (`tasks.dashboard`), assigned to the source owner, created through the Asana
    MCP after the analyst approves it.
  - `tasks:` block: add `dashboard`.
- [ ] **Step 2: Edit `cube-validation-answers`:**
  - Step 1: the question JSON's `codes` and `profiles`.
  - The answer table and step 5: `fix_source` drafts an Asana subtask under the
    validation file's `tasks.dashboard`, assigned to whoever the owner names,
    with the code's profile; the owner approves, the session creates it, and its
    link is the answer's `task`.
  - The example and rule: a code-group question takes 1 answer entry per code,
    each listing only that code's decision ids from `codes`.
- [ ] **Step 3: Lint** from the worktree root:
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/cube-validation/SKILL.md .claude/skills/cube-validation-answers/SKILL.md </dev/null`.
      Expected: no lint issues (formatting is the commit hook's).
- [ ] **Step 4: Commit**
      `docs(cube): document code groups, sum mode and Asana source fixes`.

### Task 6: Whole-package check

- [ ] **Step 1: Run**
      `uv run --with duckdb pytest tests/scripts/cube_validation -q` from the
      worktree root. Expected: all PASS, none skipped for a missing `duckdb`.
- [ ] **Step 2: Run** `uv run python -m scripts.cube_validation --help` from the
      worktree root. Expected: exit 0, every command listed.
