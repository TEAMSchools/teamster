# `_dbt_source_project` Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish #3142 — every `union_relations` view exposes
`_dbt_source_project`, every `union_dataset_join_clause` call is replaced by a
`_dbt_source_project` equality, and the macro is deleted.

**Architecture:** A behavior-preserving refactor in three dependency-ordered
batches: (1) rename the producer macro and backfill the column on every union
view, (2) swap consumer joins directory-by-directory, (3) delete the legacy
macro and update docs. Each lettered sub-step is its own PR.

**Tech Stack:** dbt (BigQuery), Jinja macros, dbt contracts, sqlfluff/trunk.

## Global Constraints

- Spec:
  `docs/superpowers/specs/2026-07-22-dbt-source-project-completion-design.md`.
- Macro signature: `extract_source_project(relation="")` — qualified when an
  alias is passed, unqualified when omitted.
- **Producer gate:** a consumer join may be swapped only after **both** joined
  union views expose `_dbt_source_project`. Batch 1 fully precedes Batch 2;
  Batch 2 fully precedes Batch 3.
- **Carve-out sources** (iReady, renlearn, amplify mClass) resolve
  `_dbt_source_project` from
  `int_people__location_crosswalk.location_dagster_code_location`, NOT the
  regex.
- Contract-enforced layers (`staging/`, `marts/`) require the new column in the
  model's `properties.yml`; intermediate/`base` do not.
- All work happens in the worktree
  `/workspaces/teamster/.worktrees/cbini/refactor/claude-source-project-sweep`
  on branch `cbini/refactor/claude-source-project-sweep`. Use
  `git -C <worktree>` and run dbt with
  `--project-dir <worktree>/src/dbt/kipptaf`.
- Run `uv run dbt deps --project-dir <worktree>/src/dbt/kipptaf` once in a fresh
  worktree before any build.
- `--target prod` dbt runs are classifier-blocked; use `--target dev --defer`
  with `--state /workspaces/teamster/src/dbt/kipptaf/target/prod` (absolute).
- Lint before every push:
  `/workspaces/teamster/.trunk/tools/trunk check --force` the changed files, run
  with cwd set to the worktree.
- Commit trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. PR
  bodies ref `#3142`.

---

## Transformation patterns (referenced by every task)

**Pattern R — rename (Batch 1a):** `extract_code_location(X)` →
`extract_source_project(X)`; `extract_code_location(table="X")` →
`extract_source_project(relation="X")`; the macro definition is renamed and
gains the optional arg. No other change.

**Pattern P — producer add (Batch 1b):** in a union view's final `select`, add
the column. Prefer the no-arg form in bare-`select *` / AM04 / unit-tested
views:

```sql
-- select-* view (keep the AM04 trunk-ignore already present)
select *, extract_source_project() as _dbt_source_project,
from union_relations
```

```sql
-- explicit / qualified-star view
select ur.*, extract_source_project("ur") as _dbt_source_project,
from union_relations as ur
```

**Pattern I — inline → macro (Batch 1b):** replace an inline
`regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project`
with `extract_source_project() as _dbt_source_project` (or the qualified form if
the inline was qualified).

**Pattern X — crosswalk (Batch 1c):** the model must join
`int_people__location_crosswalk` on its school/location column and project:

```sql
lc.location_dagster_code_location as _dbt_source_project,
```

If the model lacks a location join, add it
(`left join {{ ref("int_people__location_crosswalk") }} as lc on <school> = lc.location_name`).

**Pattern S — consumer swap (Batch 2):** in a join clause, replace the macro:

```sql
-- before
inner join {{ ref("other_union_model") }} as b
    on a.id = b.id
    and {{ union_dataset_join_clause(left_alias="a", right_alias="b") }}

-- after
inner join {{ ref("other_union_model") }} as b
    on a.id = b.id
    and a._dbt_source_project = b._dbt_source_project
```

If alias `a` or `b` does not yet expose `_dbt_source_project`, add it to that
CTE's `select` first (it originates from the union view fixed in Batch 1).

**Pattern C — contract column:** for a contracted producer/consumer, add to
`properties.yml`:

```yaml
- name: _dbt_source_project
  data_type: string
  description: KIPP region code location derived from the source relation.
```

---

## Batch 1a — Rename the macro (1 PR)

**Files:**

- Modify: `src/dbt/kipptaf/macros/utils.sql` (macro def)
- Modify: all files calling `extract_code_location` (~45 producer sites + 2
  non-producer sites `int_students__fldoe_fte.sql`,
  `qa_edplan__powerschool_mismatch.sql`)

**Interfaces:**

- Produces: macro `extract_source_project(relation="")`.

- [ ] **Step 1: Rewrite the macro definition**

```sql
{% macro extract_source_project(relation="") %}
    regexp_extract(
        {% if relation %}{{ relation }}.{% endif %}_dbt_source_relation,
        r'(kipp\w+)_'
    )
{% endmacro %}
```

(Delete the old `extract_code_location` macro. Leave `union_dataset_join_clause`
and `extract_region` untouched — `union_dataset_join_clause` still references
the old name, so update its body to call `extract_source_project`.)

- [ ] **Step 2: Sweep all call sites** — replace `extract_code_location(` with
      `extract_source_project(` and the keyword `table=` with `relation=`:

Run (from worktree):

```bash
grep -rl 'extract_code_location' src/dbt/kipptaf --include='*.sql' \
  | xargs sed -i 's/extract_code_location(table=/extract_source_project(relation=/g; s/extract_code_location(/extract_source_project(/g'
```

- [ ] **Step 3: Verify no references remain**

Run: `grep -rn 'extract_code_location' src/dbt/kipptaf` → Expected: only the
docs/CLAUDE.md prose (fixed in Batch 3); **0** in `*.sql`.

- [ ] **Step 4: Compile to confirm identical render**

Run: `uv run dbt parse --project-dir src/dbt/kipptaf --target dev` Expected:
parses with no macro-resolution errors.

- [ ] **Step 5: Lint**

Run: `/workspaces/teamster/.trunk/tools/trunk check --force <changed .sql>` (cwd
= worktree). Expected: no new issues.

- [ ] **Step 6: Commit + push + PR**

```bash
git -C <worktree> add -u
git -C <worktree> commit -m "refactor(dbt): rename extract_code_location to extract_source_project (#3142)"
git -C <worktree> push
```

PR body: "Mechanical rename, behavior-preserving. Refs #3142."

---

## Batch 1b — Backfill regex-producers (3 PRs)

All 53 regex-producers apply **Pattern P** (or **Pattern I** for the 9 inline
copies), plus **Pattern C** for the `staging*` ones. **Skip disabled
integrations** — they will not build: `adp/workforce_now/fivetran/*` and
`illuminate/fivetran/*` (per `kipptaf/CLAUDE.md` disabled list). Apply the macro
to them for consistency but note in the PR they are unverifiable locally.

### PR 1b-1 — powerschool (30 files)

**Files (Modify SQL + `properties.yml` for `stg_*`):**
`int_powerschool__calendar_rollup`, `int_powerschool__category_grades_pivot`,
`int_powerschool__district_entry_date`, `int_powerschool__final_grades_pivot`,
`int_powerschool__gradescaleitem_lookup`,
`int_powerschool__section_grade_config`, `int_powerschool__teachers`,
`stg_powerschool__attendance`, `stg_powerschool__attendance_code`,
`stg_powerschool__cc`, `stg_powerschool__fte`, `stg_powerschool__gen`,
`stg_powerschool__gpnode`, `stg_powerschool__gpprogresssubject`,
`stg_powerschool__gpprogresssubjectearned`,
`stg_powerschool__gpprogresssubjectenrolled`, `stg_powerschool__log`,
`stg_powerschool__pgfinalgrades`, `stg_powerschool__roledef`,
`stg_powerschool__s_stu_x`, `stg_powerschool__sectionteacher`,
`stg_powerschool__studentrace`, `stg_powerschool__studenttest`,
`stg_powerschool__studenttestscore`, `stg_powerschool__terms`,
`stg_powerschool__test`, `stg_powerschool__testscore`,
`stg_powerschool__u_storedgrades_de`, `stg_powerschool__users`,
`stg_powerschool__userscorefields`

- [ ] **Step 1:** Apply Pattern P to each SQL (Pattern I where inline already
      exists), Pattern C to each `stg_*` `properties.yml`. Inspect each: if it
      is a bare `select *` with an AM04 trunk-ignore, use
      `extract_source_project()` (no arg); if `select ur.*`/explicit, use
      `extract_source_project("ur")`.
- [ ] **Step 2: Build + verify column present, row count unchanged**

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --select stg_powerschool__cc stg_powerschool__terms int_powerschool__teachers  # (repeat/expand for the set)
```

Expected: all build; `_dbt_source_project` populated with `kipp*` values;
per-model row count equals prod baseline.

- [ ] **Step 3: Lint** the changed `.sql`/`.yml`.
- [ ] **Step 4: Commit + push + PR**
      (`refactor(dbt): add _dbt_source_project to powerschool union views (#3142)`).

### PR 1b-2 — assessment sources (illuminate-dlt + pearson + fldoe)

**Files:** `int_illuminate__agg_student_responses` (dlt),
`int_illuminate__repository_data`, `stg_illuminate__national_assessments__psat`,
`stg_pearson__student_list_report`, `stg_pearson__student_test_update`,
`int_fldoe__fast_standard_performance_unpivot`. (Disabled,
apply-but-unverifiable: `int_illuminate__agg_student_responses` (fivetran),
`stg_illuminate__aptest`, `stg_illuminate__psat`, `stg_illuminate__psat89`.)

- [ ] Steps as PR 1b-1 (Patterns P/I + C), building the enabled models.

### PR 1b-3 — misc sources (deanslist + overgrad + finalsite + schoolmint + titan + zendesk)

**Files:** `int_deanslist__incidents__attachments`,
`int_deanslist__students__custom_fields__pivot`, `stg_deanslist__behavior`,
`stg_deanslist__terms`, `stg_deanslist__users`, `int_overgrad__admissions`,
`stg_overgrad__admissions`, `stg_finalsite__status_report`,
`stg_schoolmint_grow__generic_tags`, `stg_titan__income_form_data`,
`int_zendesk__ticket_metrics_union`. (Disabled, apply-but-unverifiable:
`int_adp_workforce_now__person_communication_pivot`,
`int_adp_workforce_now__worker_organizational_unit_pivot`.)

- [ ] Steps as PR 1b-1.

---

## Batch 1c — Crosswalk carve-out (1 PR)

**Files (all apply Pattern X + Pattern C for `stg_*`):**

- iReady: `int_iready__instruction_by_lesson`,
  `int_iready__instruction_by_lesson_pro`,
  `int_iready__instructional_usage_data`,
  `int_iready__personalized_instruction_unpivot`,
  `stg_iready__personalized_instruction_summary`
- renlearn: `stg_renlearn__fast_star`, `stg_renlearn__star_dashboard_standards`
- amplify mClass: `stg_amplify__mclass__sftp__benchmark_student_summary`,
  `stg_amplify__mclass__sftp__pm_student_summary`,
  `stg_amplify__mclass__sftp__pm_student_summary_aimline`
- Reference (already crosswalk-resolved, normalize pattern to match):
  `stg_renlearn__star`, `int_iready__diagnostic_results`,
  `int_amplify__mclass__benchmark_student_summary`,
  `int_amplify__mclass__pm_student_summary`

- [ ] **Step 1: Verify each unions a shared/non-region relation** — confirm the
      model unions a `kippnj_*` source (iReady/renlearn) or a method-keyed union
      (amplify). If a listed model instead unions region-bearing relations, use
      Pattern P/I (macro) rather than Pattern X.
- [ ] **Step 2:** Apply Pattern X (add the `int_people__location_crosswalk` join
      where absent; project
      `location_dagster_code_location as _dbt_source_project`). Add Pattern C to
      the `stg_*` `properties.yml`.
- [ ] **Step 3: Build + verify home region** — a Newark iReady/renlearn row
      reads `kippnewark` (NOT `kippnj`); a Camden row reads `kippcamden`; row
      counts match prod.

```bash
uv run dbt build --project-dir src/dbt/kipptaf --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --select stg_renlearn__fast_star int_iready__instruction_by_lesson
```

- [ ] **Step 4: Lint. Step 5: Commit + push + PR**
      (`refactor(dbt): resolve _dbt_source_project via crosswalk for iready/renlearn/amplify (#3142)`).

---

## Batch 2 — Consumer join swaps (Pattern S), by directory

**Gate:** run this only after all Batch 1 PRs merge. Before each PR, for every
`union_dataset_join_clause` call in its files, confirm both aliased CTEs expose
`_dbt_source_project` (grep the compiled SQL); if not, thread it through the
CTE.

Common per-PR cycle for each task below:

- [ ] Apply Pattern S to every `union_dataset_join_clause` in the file set;
      thread the column through CTEs as needed; add Pattern C for contracted
      models.
- [ ] Build the changed models `--target dev --defer`; confirm **row count and
      distinct-key count equal the prod baseline** (algebraic identity → exact
      match).
- [ ] Lint; commit; push; PR
      (`refactor(dbt): swap union_dataset_join_clause in <dir> (#3142)`).

### PR 2a-1 — tableau gradebook family

`rpt_tableau__gradebook_dashboard`, `rpt_tableau__gradebook_assignments`,
`rpt_tableau__gradebook_gpa`, `rpt_tableau__assignment_checks`,
`rpt_tableau__student_course_grades`, `rpt_tableau__qbl`.

### PR 2a-2 — tableau assessment/state family

`rpt_tableau__state_assessments_dashboard`, `rpt_tableau__assessment_dashboard`,
`rpt_tableau__ddi_dashboard`, `rpt_tableau__college_assessment_dashboard_de`,
`rpt_tableau__college_assessment_dashboard_historic`,
`rpt_tableau__state_testing_accomodations`, `rpt_tableau__power_standards`,
`rpt_tableau__academic_goals_rollup`, `rpt_tableau__iready_apm`,
`rpt_tableau__miami_k2_iready`, `rpt_tableau__dibels_dashboard`,
`rpt_tableau__graduation_requirements`.

### PR 2a-3 — tableau attendance/culture/misc family

`rpt_tableau__attendance_dashboard`,
`rpt_tableau__attendance_chronic_absenteeism_log`,
`rpt_tableau__suspension_over_time`, `rpt_tableau__consequence_dashboard`,
`rpt_tableau__okrts_behavior`, `rpt_tableau__school_culture_dashboard_nj`,
`rpt_tableau__mtss_rti`, `rpt_tableau__community_service`,
`rpt_tableau__home_instruction`, `rpt_tableau__home_instruction_queue`,
`rpt_tableau__hs_early_warning_dashboard`, `rpt_tableau__crdc_roster`,
`rpt_tableau__nj_school_register`, `rpt_tableau__gpa_analysis`,
`rpt_tableau__student_info_audit`,
`rpt_tableau__student_attrition_over_time_v1`, `rpt_tableau__ops_dashboard`.

### PR 2b — tableau intermediate

`int_tableau__gradebook_audit_student_scaffold`,
`int_tableau__gradebook_audit_teacher_scaffold`,
`int_tableau__gradebook_audit_categories_teacher`,
`int_tableau__gradebook_audit_assignments_teacher`,
`int_tableau__gradebook_audit_assignments_student`,
`int_tableau__state_assessments_demographic_comps`.

### PR 2c — extracts/google (12)

`rpt_gsheets__nj_state_test_roster`, `rpt_gsheets__athletic_eligibility`,
`rpt_gsheets__kippfwd_miami_roster`, `rpt_gsheets__csgf_hs_enrollment`,
`rpt_gsheets__csgf_hs_ap_offerings`, `rpt_gsheets__grad_plan_tracking`,
`rpt_gsheets__award_ceremony_gpa`, `rpt_gsheets__mtss_rti`,
`rpt_gsheets__absence_streak_roster`, `rpt_gsheets__school_metrics_extract`,
`rpt_gsheets__gpa_roster`, `rpt_gsheets__gpa_flags_report`,
`int_google_sheets__dibels_pm_expectations` (13 incl. the intermediate).

### PR 2d — extracts/deanslist + clever + powerschool + littlesis (13)

`rpt_deanslist__promo_status`, `rpt_deanslist__student_misc`,
`rpt_deanslist__transcript_gpas`, `rpt_deanslist__final_grades`,
`rpt_deanslist__hs_transcript_programs`, `rpt_deanslist__state_test_scores`,
`rpt_deanslist__designations`, `rpt_deanslist__transcript_grades`,
`rpt_clever__enrollments`, `rpt_clever__sections`,
`rpt_powerschool__autocomm_students`, `rpt_powerschool__autocomm_teachers`,
`rpt_littlesis__enrollments`.

### PR 2e — non-extract consumers (18)

`int_students__contacts`, `int_students__athletic_eligibility`,
`int_extracts__student_enrollments_subjects`,
`int_assessments__course_enrollments`, `int_kippadb__roster`,
`int_powerschool__state_assessments_transfer_scores`, `int_powerschool__log`,
`int_powerschool__ps_adaadm_daily_ctod`, `int_powerschool__gpnode`,
`int_powerschool__gpprogress_grades`, `base_powerschool__sections`,
`int_reporting__promotional_status`, `int_topline__gpa_term_weekly`,
`int_topline__iready_diagnostic_weekly`, `int_topline__gpa_cumulative_weekly`,
`bridge_course_section_teachers`, `fct_family_communications`, `dim_students`.

**Ordering within 2e:** some of these are themselves union producers feeding
others (`int_powerschool__gpnode` → `int_powerschool__gpprogress_grades` →
`int_topline__gpa_term_weekly`). Do producer models before their consumers
within the PR; keep each model's own swap atomic.

### PR 2f — qa + tests + analyses (5)

`qa_powerschool__transfer_records`, `qa_edplan__powerschool_mismatch`,
`test_incorrect_student_number_pearson`,
`collegeboard_ap_tiered_crosswalk_match`,
`collegeboard_ap_downstream_lineage_root_cause`. (Also convert the 2
non-producer `extract_source_project` filter/alias sites in
`int_students__fldoe_fte` — done in 2e with `int_students__` — and
`qa_edplan__powerschool_mismatch` to plain `_dbt_source_project` refs.)

---

## Batch 3 — Macro removal + docs (1 PR)

**Files:**

- Modify: `src/dbt/kipptaf/macros/utils.sql` (delete
  `union_dataset_join_clause`)
- Modify: `src/dbt/kipptaf/CLAUDE.md`, `src/dbt/kipptaf/models/marts/CLAUDE.md`
- Verify: the 7 half-migrated files carry no residual macro call

- [ ] **Step 1: Confirm 0 call sites**

Run: `grep -rn 'union_dataset_join_clause' src/dbt/kipptaf --include='*.sql'`
Expected: **0** results.

- [ ] **Step 2: Delete the macro** from `utils.sql`.
- [ ] **Step 3: Rewrite the docs** — in `kipptaf/CLAUDE.md`, replace the
      `union_dataset_join_clause (critical)` section with the new rule: "Union
      views expose `_dbt_source_project` via `extract_source_project()`; join on
      it directly. Exception: crosswalk-resolved sources
      (iReady/renlearn/amplify mClass) derive it from
      `int_people__location_crosswalk`." Remove the "prefer inline" guidance.
      Update the `marts/CLAUDE.md` hash-and-join note.
- [ ] **Step 4: Reconcile half-migrated files** — grep the 7 files; ensure none
      still calls the macro (all should have been swapped in Batch 2).
- [ ] **Step 5: Compile** (`dbt parse --target dev`) — Expected: no
      `union_dataset_join_clause` resolution errors (proves nothing still calls
      it).
- [ ] **Step 6: Lint** (include the `*.md`:
      `trunk check --force --no-fix </dev/null <files>`).
- [ ] **Step 7: Commit + push + PR**
      (`refactor(dbt): remove union_dataset_join_clause macro; update docs (closes #3142)`).

---

## Self-review notes

- **Spec coverage:** macro rename (1a) ✓, backfill all 124 = 61 existing + 63
  new split regex(1b)/carve-out(1c) ✓, inline→macro ✓, consumer swaps all 263/90
  files (2a-2f) ✓, macro delete + docs (3) ✓, contract columns (Pattern C) ✓,
  carve-out (1c) ✓, half-migrated reconciliation (3) ✓.
- **Producer gate** enforced by batch ordering + the pre-swap compiled-SQL
  check.
- **Disabled integrations** (adp/illuminate Fivetran) flagged as
  apply-but-unverifiable, not silently skipped.

---

## Execution findings — scope refinement (discovered during Batch 1)

The plan's "backfill 63 producers" over-counted. The real rule is **backfill
every _cross-district (region)_ union view**, not literally every
`union_relations` view. A union view whose `_dbt_source_relation` encodes a
_non-region_ dimension must be **excluded** — a region regex would yield null.

**Excluded (non-region unions), verified during execution:**

- **illuminate** — unions response-types (`_standard`/`_group`), repository ids,
  and assessment years, never districts.
- **zendesk** (`int_zendesk__ticket_metrics_union`) — unions current + archive.
- **schoolmint_grow** (`stg_schoolmint_grow__generic_tags`) — unions tag-types.
- **adp / illuminate Fivetran** — disabled integrations.
- **renlearn** `stg_renlearn__fast_star`,
  `stg_renlearn__star_dashboard_standards` — union `kippmiami_renlearn` ONLY
  (FAST is a Florida assessment, Miami-only), so `_dbt_source_project` would be
  a constant `kippmiami` with nothing to disambiguate; they also lack a
  school/location column (only `school_year`). Not region-joined (`fast_star`
  has no consumers; `star_dashboard_standards` joins its STAR subquery on
  `assessment_id`). (The shared `kippnj_renlearn` schema applies to
  `stg_renlearn__star`, which is a different, already-resolved model.)
- **iReady** secondary models (`int_iready__instruction_by_lesson`(`_pro`),
  `int_iready__instructional_usage_data`,
  `int_iready__personalized_instruction_unpivot`,
  `stg_iready__personalized_instruction_summary`) — none use
  `union_dataset_join_clause` or expose `_dbt_source_project` (some
  crosswalk-rewrite `_dbt_source_relation` internally but do not project the
  column); only `int_iready__diagnostic_results` projects it, and it already has
  it.
- **amplify mClass sftp staging** — region is resolved one level up in
  `int_amplify__mclass__benchmark_student_summary` /
  `int_amplify__mclass__pm_student_summary` (crosswalk), which already have it.

**Batch 1c is therefore a no-op for code.** The carve-out sources'
region-relevant models (`stg_renlearn__star`, `int_iready__diagnostic_results`,
`int_amplify__mclass__*`) already carry `_dbt_source_project` from PR #4024.

**Batch 1 (producer backfill) is complete** across PRs #4503 / #4504 / #4505.

**Batch 2 gating (stronger than stated):** a consumer whose join alias reads a
**snapshot** (e.g. `int_topline__gpa_term_weekly` reads
`snapshot_powerschool__gpa_term`) cannot expose `_dbt_source_project` on that
side until the producer PR **merges and the snapshot re-runs in prod** — so
Batch 2 is gated on Batch 1 _merging_, not just the branch carrying the columns.

**Two recurring build-only bugs** (both lint/parse-clean, fail at BigQuery
build):

- bare `extract_source_project()` without `{{ }}` → "Function not found".
- per-model `contract: enforced: true` set in `properties.yml` (not the
  directory default) → a `select *` wrap breaks the contract unless the column
  is added to the yml. Check per file.
