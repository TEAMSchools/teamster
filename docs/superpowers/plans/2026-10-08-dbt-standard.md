# dbt SQL and Model Design Standard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** One dbt standard (architecture + SQL style) that lives in the Claude
rule files, publishes to the docs site, and is enforced by lint, a manifest
check with a baseline ratchet, and claude-review.

**Architecture:** Rule files under `.claude/rules/` hold every rule with a
stable ID; `pymdownx.snippets` includes their human-facing sections into
`docs/reference/dbt-conventions.md`. A PEP 723 script reads `manifest.json` to
enforce layer edges and touched-model rules; a regex script backs a trunk custom
linter for banned BigQuery syntax.

**Tech Stack:** Markdown, MkDocs Material + pymdownx.snippets, dbt (BigQuery),
Python 3.12+ (stdlib only), pytest, trunk, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-07-dbt-standard-design.md`

## Global Constraints

- Issue #5789. PR 1 body carries `Refs #5789`; PR 2 uses `Closes #5789`.
- 2 PRs:
  - PR 1, the standard (Tasks 1-4): `cbini/feat/claude-dbt-standard` (exists;
    holds the spec and this plan). Docs, rule files, and the claude-review
    prompt. It merges first: the prompt reads the rule files it adds.
  - PR 2, enforcement (Tasks 5-9): `cbini/feat/claude-dbt-enforcement`, created
    after PR 1 merges with `gh issue develop 5789 --name <branch>` then
    `git worktree add /workspaces/teamster/.claude/worktrees/<branch> <branch>`.
    The `trunk.yaml` block for the user goes in its body.
- Never sweep existing models. The standard applies to new and touched code;
  layer violations go in the baseline.
- Rule IDs are stable once published: `A1…` architecture, `S1…` style, and the
  mart rubric keeps `R1…R10` unchanged.
- Every rule inside a snippet section has: rule (1 sentence), why (1 line), good
  and bad example, `Enforced by:` (check name or `review`).
- `.trunk/trunk.yaml`, `settings.json` and hook scripts are Edit-denied: draft
  the change in the PR body and hand it to the user.
- Scripts are stdlib-only PEP 723 scripts in `scripts/`, tested by loading them
  with `importlib.util.spec_from_file_location` (see `scripts/CLAUDE.md`).
- Run dbt only as `uv run dbt ... --project-dir <worktree>/src/dbt/<project>`;
  invoke `dbt-local-dev` before any local dbt command.
- Lint before each push:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`.

## Review Focus

- A kipptaf `source()` pointing at a district or package table whose name has no
  layer prefix (raw `src_*`, snapshots, BigQuery-native archives) must be
  classified `source`, never crash or count as a violation.
- Disabled models, tests, seeds, analyses and exposures without `depends_on`
  must be skipped, not classified.
- A model name present in both a package and kipptaf
  (`int_finalsite__student_contacts`) must be keyed by `unique_id`, never by
  name.
- A changed `properties.yml` (no `.sql` change) must map to its model through
  `patch_path`, so the touched-model rules still run.
- In a non-kipptaf project, the whole project is 1 source folder; no edge inside
  it is a cross-source violation.

---

## Part 1: the standard (PR 1)

### Task 1: `.claude/rules/dbt-architecture.md`

**Files:**

- Create: `.claude/rules/dbt-architecture.md`
- Modify: `src/dbt/kipptaf/models/marts/CLAUDE.md` (move _Column-naming rubric_,
  _Degenerate-dim rule_, _Plumbing definition_, _Strict-chain traversal_, _PK /
  FK / date column shapes_ out; leave a 1-line pointer)
- Modify: `src/dbt/CLAUDE.md` _Model Conventions_ list (add the new file)

**Interfaces:**

- Produces: snippet section `architecture`, delimited by
  `<!-- --8<-- [start:architecture] -->` and
  `<!-- --8<-- [end:architecture] -->`. Rule IDs below, cited by Tasks 4 and
  7-9.

- [ ] **Step 1: Write the file.** Frontmatter
      `paths: ["**/src/dbt/**/models/**"]`. Inside the section, write these
      rules from spec section 2:

| ID  | Rule                                                                    | Enforced by                        |
| --- | ----------------------------------------------------------------------- | ---------------------------------- |
| A1  | Each layer reads only its allowed layers (the edges table)              | `dbt-layer-check` (baseline)       |
| A2  | An `rpt_` reads a mart when 1 covers the entity; else links an issue    | review                             |
| A3  | A new `int_` is build (no suffix) or reshape (5 suffixes)               | `dbt-layer-check`                  |
| A4  | 1 model per grain per source folder, 1 across domain folders            | review + `dbt-layer-check` warning |
| A5  | Dedup only in `stg_` or source `int_`                                   | review                             |
| A6  | Long in the core, wide at the edge                                      | review                             |
| A7  | Identity in domain `int_`; entity keys only through their macro         | `dbt-layer-check`                  |
| A8  | Exposures depend only on `rpt_` and marts; Cube only on marts           | `dbt-layer-check` (baseline)       |
| A9  | No `select *` in the final select of an `rpt_` or mart                  | `dbt-layer-check`                  |
| A10 | Join unioned regional models on `_dbt_source_project`                   | review                             |
| A11 | Domain folders are tagged `+meta: {layer: domain}` in `dbt_project.yml` | `dbt-layer-check`                  |

      Then the moved mart rubric `R1`-`R10` (text unchanged) and strict-chain
      rules inside the same section. Put the layer table, edges table, and
      other-projects paragraph from spec section 2 above the rules.

- [ ] **Step 2: Lint** the 3 files. Expected: `✔ No issues`.
- [ ] **Step 3: Commit** `docs(dbt): add the architecture rule file`.

### Task 2: restructure `.claude/rules/dbt-sql.md`

**Files:**

- Modify: `.claude/rules/dbt-sql.md`

**Interfaces:**

- Produces: snippet section `sql-style`; rule IDs below.

- [ ] **Step 1: Restructure.** Top of file: the `sql-style` section with these
      rules, then everything else (Tier 3) below it, unchanged except where a
      rule moved up:

| ID  | Rule                                                                         | Enforced by            |
| --- | ---------------------------------------------------------------------------- | ---------------------- |
| S1  | ANSI SQL or a dbt macro first; no `qualify`, `group by all`, `corresponding` | `sql-banned-syntax`    |
| S2  | No positional `group by`                                                     | sqlfluff AM06          |
| S3  | No subqueries against tables or CTEs (`unnest` aggregate carve-out)          | sqlfluff ST05 + review |
| S4  | No pass-through import CTEs                                                  | review                 |
| S5  | No `order by` in models                                                      | review                 |
| S6  | Select-list complexity order (the 7 buckets) — house rule                    | review                 |
| S7  | sqlfluff ST06 select order (separate heading from S6)                        | sqlfluff ST06          |
| S8  | Max 1 level of function nesting                                              | review                 |
| S9  | Cast early, once, with an explicit alias                                     | review                 |
| S10 | No row-level calculations in `where` or one-sided ones in `on`               | review                 |
| S11 | Row filters on the preserved table go in `where`, not `on`                   | review                 |
| S12 | `distinct` only for grain projection, annotated                              | review                 |
| S13 | Half-open intervals for abutting date ranges                                 | review                 |
| S14 | Booleans `is_`/`has_`; Y/N text only inside an `rpt_` that needs it          | review                 |
| S15 | `if()` for 1 condition, `case` for 2+                                        | review                 |
| S16 | Table aliases: short initials from the model name, unique in the query       | review                 |
| S17 | `union all` branches enumerate the same columns in the same order            | review                 |
| S18 | Comments say only what the line cannot show; rationale goes in YAML          | review                 |

      Add the dbt Labs deviations table (spec section 3) and the 8-item review
      rubric, each item citing its IDs. Remove the claim that ST06 enforces the
      7-bucket order.

- [ ] **Step 2: Lint**. Expected: `✔ No issues`.
- [ ] **Step 3: Commit** `docs(dbt): give SQL style rules stable IDs`.

### Task 3: published page

**Files:**

- Modify: `mkdocs.yml` (add extension)
- Modify: `docs/reference/dbt-conventions.md` (becomes the stub)
- Modify: `.github/workflows/mkdocs-gh-deploy.yaml` (trigger path)
- Modify: `docs/CLAUDE.md` _Available Markdown Extensions_ (add snippets)

**Interfaces:**

- Consumes: sections `architecture` and `sql-style` from Tasks 1-2.

- [ ] **Step 1: Enable snippets** in `mkdocs.yml`:
      `pymdownx.snippets: {base_path: ["."], check_paths: true}`.
- [ ] **Step 2: Rewrite the stub.** Order: the change-process paragraph (spec
      section 1, last bullet);
      `--8<-- ".claude/rules/dbt-architecture.md:architecture"`;
      `--8<-- ".claude/rules/dbt-sql.md:sql-style"`; then a "Reference" section
      keeping today's non-rule content (diacritics, time travel, UDF table,
      properties-file shape, exposures). Delete the 2 statements that conflict
      with the rules (pass-through CTEs fine; `DISTINCT` free-text comment).
- [ ] **Step 3: Add** `.claude/rules/dbt-*.md` to `paths:` in
      `mkdocs-gh-deploy.yaml`.
- [ ] **Step 4: Build.** Run
      `uv run --group docs mkdocs build --strict --site-dir <scratchpad>/site`
      from the worktree. Expected: exit 0. Then
      `grep -c 'A1' <scratchpad>/site/reference/dbt-conventions/index.html` ≥ 1
      and `grep -c 'paths:' …/index.html` = 0 (frontmatter excluded). If the
      markers inside HTML comments are not recognized, use bare
      `--8<-- [start:x]` lines and re-check.
- [ ] **Step 5: Lint, commit**
      `docs(dbt): publish the standard from the rule files`.

### Task 4: review prompt cites rule IDs

**Files:**

- Modify: `.github/workflows/claude-code-review.yaml` (prompt, lines 76-84)

- [ ] **Step 1: Replace** the SQL paragraph: read
      `.claude/rules/dbt-architecture.md` and `.claude/rules/dbt-sql.md` with
      the Read tool; check only rules whose `Enforced by` is `review`; cite the
      rule ID in every SQL or dbt finding; never report a rule enforced by
      sqlfluff, `sql-banned-syntax`, or `dbt-layer-check`. Keep the
      model-altitude paragraph.
- [ ] **Step 2: Verify** the YAML parses after the fmt hook:
      `uv run python -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" .github/workflows/claude-code-review.yaml`.
      Expected: no error. The PR's own review run is the live test: its findings
      cite IDs.
- [ ] **Step 3: Commit, push, open PR 1** (spec, plan, Tasks 1-4) with
      `Refs #5789`.

## Part 2: enforcement (PR 2)

Create the PR 2 branch and worktree first (Global Constraints).

### Task 5: `src/dbt/kipptaf/macros/entity_keys.sql`

**Files:**

- Create: `src/dbt/kipptaf/macros/entity_keys.sql`

**Interfaces:**

- Produces: 1 macro per entity whose key is hashed in 2+ marts. Confirmed by
  grep on 2026-10-08: `student_key(student_number)`,
  `staff_key(employee_number)`, `work_assignment_key(item_id)`,
  `region_key(business_unit_code)`, `survey_key(survey_id)`,
  `college_key(college_code_branch)`, `job_candidate_key(candidate_id)`. Each
  takes the column expression(s) as strings plus `nullable=false`;
  `nullable=true` emits the
  `if(<col> is not null, <hash>, cast(null as string))` wrap from
  `.claude/rules/dbt-sql.md`.

- [ ] **Step 1: Re-run the inventory**, including composite keys:
      `rg -U -o 'generate_surrogate_key\(\s*\[[^\]]*\]\s*\)[^,]{0,60}as \w+_key' src/dbt/kipptaf/models/marts`.
      Add a macro for any other key hashed in 2+ models with the same inputs. Do
      not add `teacher_staff_key` to `staff_key`: it hashes `internal_id_int`,
      not `employee_number`. List it in the PR as an open question.
- [ ] **Step 2: Write a failing check.** For each macro, compare
      `uv run dbt compile --inline "select {{ student_key('student_number') }}"`
      with
      `--inline "select {{ dbt_utils.generate_surrogate_key(['student_number']) }}"`.
      Before the macro exists: compile error.
- [ ] **Step 3: Implement** the macros.
- [ ] **Step 4: Verify.** Each pair's compiled SQL is byte-identical; also
      compare the `nullable=true` form against the documented `if(...)` wrap.
- [ ] **Step 5: Commit** `feat(dbt): add entity key macros`. No mart changes;
      marts adopt the macros when touched.

### Task 6: sqlfluff settings and banned-syntax linter

**Files:**

- Modify: `.trunk/config/.sqlfluff`
- Create: `scripts/check_sql_banned_syntax.py`
- Test: `tests/scripts/test_check_sql_banned_syntax.py`

**Interfaces:**

- Produces: `find_banned(sql: str) -> list[tuple[int, int, str, str]]` returning
  `(line, col, rule_code, message)`; CLI prints
  `{path}:{line}:{col}: [error] {message} ({rule_code})` per hit, exit 1 if any.
  Codes: `S1-qualify`, `S1-group-by-all`, `S1-corresponding`.

- [ ] **Step 1: Write failing tests**: `qualify row_number() over (...) = 1` → 1
      hit `S1-qualify`; `group by all` → `S1-group-by-all`;
      `full union all corresponding` → `S1-corresponding`; the same words in a
      `--` comment, a `{# #}` comment, a string literal (`'qualify'`), or a
      column name (`is_qualifying`) → 0 hits; uppercase `QUALIFY` → 1 hit.
- [ ] **Step 2: Run**
      `uv run pytest tests/scripts/test_check_sql_banned_syntax.py -v`.
      Expected: FAIL (module missing).
- [ ] **Step 3: Implement** with word-boundary regexes after blanking comments
      and string literals (keep line/column positions).
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: sqlfluff config.** Add
      `[sqlfluff:rules:ambiguous.column_references]`
      `group_by_and_order_by_style = explicit` and
      `[sqlfluff:rules:structure.subquery]` `forbid_subquery_in = both`.
- [ ] **Step 6: Verify config.** Write a scratch model under `.claude/scratch/`
      with the blessed `(select min(x) from unnest([...]) as x)` form and a
      `group by 1`; run trunk check on it. Expected: AM06 fires on `group by 1`,
      ST05 does not fire on the `unnest` form. Then confirm hold-the-line: edit
      1 untouched line of a model that uses `group by 1` and run `trunk check`
      (no `--force`); expected: no AM06 on unchanged lines. Record both results
      in the PR.
- [ ] **Step 7: Draft the trunk.yaml block** in the PR body for the user: a
      `lint.definitions` entry `sql-banned-syntax` running
      `uv run scripts/check_sql_banned_syntax.py ${target}` on `sql` files under
      `src/dbt/**`, `output: regex` with
      `parse_regex: "(?P<path>.*):(?P<line>\d+):(?P<col>\d+): \[(?P<severity>[^\]]*)\] (?P<message>.*) \((?P<code>[^)]*)\)"`,
      plus `sql-banned-syntax` in `lint.enabled`. Verify the definition keys
      against trunk's custom-linter docs (context7) before handing it over.
- [ ] **Step 8: Commit** `feat(dbt): lint banned SQL syntax and subqueries`.

### Task 7: layer classification and edges (A1, A8)

**Files:**

- Create: `scripts/check_dbt_standard.py`
- Test: `tests/scripts/test_check_dbt_standard.py`
- Create: `tests/scripts/fixtures/dbt_standard_manifest.json` (hand-built, about
  15 nodes)

**Interfaces:**

- Produces:
  - `dataclass(frozen=True) class Violation: model: str; rule: str; detail: str; severity: Literal["error", "warning"]; message: str`.
    Baseline key is `(model, rule, detail)`; `detail` is the offending parent or
    child name.
  - `layer_of(node: dict, project: str, domain_folders: set[str]) -> str`, one
    of `source`, `stg`, `source_int`, `domain_int`, `mart`, `rpt`, `snapshot`,
    `other`. Marts are `dim_`/`fct_`/`bridge_`; `base_` is `domain_int`; an
    `int_` is `domain_int` when its top folder under `models/` is in
    `domain_folders`, and only in kipptaf.
  - `source_folder(node: dict, project: str) -> str`: the top folder under
    `models/` in kipptaf; the project name elsewhere.
  - `check_edges(manifest: dict, project: str, domain_folders: set[str]) -> list[Violation]`
    over all enabled models and exposures (rules `A1`, `A8`).
  - `ALLOWED: dict[str, set[str]]`, transcribed from spec section 2's edges
    table. A kipptaf `source()` to a district table takes the layer of the
    table-name prefix; unprefixed → `source`.

- [ ] **Step 1: Write failing tests**, 1 per row of the edges table (allowed and
      disallowed case each), plus: `rpt_` → `rpt_` is `A1`; source `int_`
      reading another source folder's `stg_` is `A1`; a Tableau exposure on an
      `int_` is `A8`; the `cube_semantic_layer` exposure on an `rpt_` is `A8`;
      the Review Focus cases (unprefixed source table, disabled node, duplicate
      name across projects, non-kipptaf project).
- [ ] **Step 2: Run tests.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(dbt): classify layers and check edges`.

### Task 8: touched-model rules (A3, A4, A7, A9) and baseline

**Files:**

- Modify: `scripts/check_dbt_standard.py`
- Modify: `tests/scripts/test_check_dbt_standard.py`

**Interfaces:**

- Consumes: `Violation`, `layer_of` (Task 7); key macro names (Task 5).
- Produces:
  - `changed_models(manifest: dict, changed_files: list[str]) -> set[str]`
    (unique_ids, matching `original_file_path` and `patch_path`).
  - `check_touched(manifest: dict, project: str, changed: set[str], added: set[str], domain_folders: set[str]) -> list[Violation]`:
    `A3` (an added `int_` whose name ends in a near-miss of a reshape suffix:
    `_pivoted`, `_unpivoted`, `_rollups`, `_rolled_up`, `_scaffolding`,
    `_unioned`, `_unions`; a name with no reshape suffix is a valid build
    model), `A7` (mart `raw_code` calls `generate_surrogate_key` for a column
    aliased `*<entity>_key`, where `<entity>_key` is in
    `KEY_MACROS = {"student_key", "staff_key", "work_assignment_key", "region_key", "survey_key", "college_key", "job_candidate_key"}`
    plus any Task 5 adds), `A9` (mart/`rpt_` final select is `select *`), `A4`
    warning (shares a uniqueness grain, minus direct parents and siblings
    sharing 1 consumer). A violation whose rule ID is a key of the node's
    `config.meta.standard_exempt` is dropped.
  - `load_baseline(path: Path) -> dict[tuple[str, str, str], str]` from a TSV
    `model\trule\tdetail\tissue`.
  - `compare(violations: list[Violation], baseline: dict) -> tuple[list[Violation], list[tuple[str, str, str]], list[tuple[str, str, str]]]`
    returning `(new, stale, missing_issue)`.
  - CLI: `--project-dir`, `--changed-files` (file), `--added-files` (file),
    `--baseline`, `--write-baseline`. Prints `::error`/`::warning` GitHub
    annotations; exit 1 on any new error, stale line, or line without an issue.

- [ ] **Step 1: Write failing tests**: each rule's hit and miss; a
      `properties.yml`-only change selects its model; `A7` catches a
      role-prefixed key (`submitter_staff_key`), catches
      `{{- dbt_utils.generate_surrogate_key(` with whitespace control, passes
      `{{ staff_key('employee_number') }}`, and ignores `staff_observation_key`;
      `standard_exempt: {A9: "..."}` drops an `A9`; `compare` reports a new
      violation, a stale baseline line, and a line with an empty issue column.
- [ ] **Step 2: Run tests.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(dbt): check touched models against the standard`.

### Task 9: domain tags, workflow, baseline, backlog issues

**Files:**

- Modify: `src/dbt/kipptaf/dbt_project.yml` (domain folder tags)
- Create: `.github/workflows/dbt-standard.yaml`
- Create: `src/dbt/standard-baseline.tsv`

- [ ] **Step 1: Pick domain folders.** Starting list: `assessments`, `extracts`,
      `finance`, `gpa`, `people`, `reporting`, `students`, `surveys`, `topline`.
      Keep a folder only if its `int_` models read 2+ source folders (check with
      `source_folder` over the prod manifest); report any difference to the user
      before tagging.
- [ ] **Step 2: Test the state risk on 1 folder.** Tag `topline` only, then
      `uv run dbt ls --project-dir <wt>/src/dbt/kipptaf --resource-type model --select state:modified --state /workspaces/teamster/src/dbt/kipptaf/target/prod | wc -l`.
      Expected if safe: same count as before tagging. If the count jumps by the
      folder's model count, drop the tags and read domain folders from a
      `DOMAIN_FOLDERS` constant in the script instead (spec section 5 fallback).
      Otherwise tag all folders.
- [ ] **Step 3: Write the workflow.** `pull_request` on `src/dbt/**`,
      `scripts/check_dbt_standard.py`, the workflow file; dependabot gate;
      `actions/checkout` and `astral-sh/setup-uv` at the same SHAs as
      `pytest.yaml`, `fetch-depth: 0`. Steps: compute changed and added files
      with
      `git diff --name-only [--diff-filter=A] origin/main...HEAD -- src/dbt`;
      for each changed project, `uv run dbt deps` and
      `uv run dbt parse --profiles-dir src/dbt/<project>`; then run the check.
- [ ] **Step 4: Write the baseline.** Run the check with `--write-baseline` over
      kipptaf and each district project; issue column empty.
- [ ] **Step 5: Group violations into issues.** Group lines by fix (usually 1
      missing mart per group). Show the user the grouping and issue titles;
      create the issues only after they confirm (bulk outward action), using the
      feature-request template, labels `enhancement` and `dbt`, and add them to
      project board 4. Fill the issue column.
- [ ] **Step 6: Verify.** Run the check locally with an empty changed list.
      Expected: exit 0. Push; expected: the `dbt-standard` workflow passes on
      the PR, which also proves `dbt parse` runs without warehouse credentials.
- [ ] **Step 7: Commit, push, open PR 2** with `Closes #5789` and the Task 6
      `trunk.yaml` block for the user.
