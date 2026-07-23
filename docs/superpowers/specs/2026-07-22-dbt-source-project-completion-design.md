# Complete #3142: `_dbt_source_project` everywhere, retire `union_dataset_join_clause`

Design spec for finishing the refactor started in
[#3142](https://github.com/TEAMSchools/teamster/issues/3142) and partially
landed in PR #4024 (assessment domain).

## Problem

Cross-district union models in `kipptaf` carry a `_dbt_source_relation` column
(added by `dbt_utils.union_relations`) whose value includes the full schema plus
table name, so it is unsafe to join two union-derived relations on it directly.
The legacy workaround is the `union_dataset_join_clause` macro, which runs
`regexp_extract(_dbt_source_relation, r'(kipp\w+)_')` on **both** sides of
**every** join, at query time.

The intended fix — materialize the extraction once per union model as a
`_dbt_source_project` column and join on it directly — was started but stalled.
The column-materialization groundwork is roughly half done; the join swap, the
macro removal, and the macro rename are almost entirely outstanding.

## Current state (measured 2026-07-22)

- `union_dataset_join_clause`: **263** call sites across **90**
  model/test/analysis files (plus the definition in `macros/utils.sql`). Down
  only ~5 from the original 268 baseline.
- `union_relations` producers: **124** total; **61** already project
  `_dbt_source_project`, **63** do not.
- Of the 61 producers that carry the column, region-extraction is forked across
  three idioms: **45** derive it via the `extract_code_location` macro, **9**
  via inline `regexp_extract(_dbt_source_relation, r'(kipp\w+)_')`, and a
  handful resolve it from `int_people__location_crosswalk` instead of the
  relation (see _Region carve-out_ below).
- **7** files are half-migrated — they carry both `_dbt_source_project` and a
  live `union_dataset_join_clause` call: `int_assessments__course_enrollments`,
  `rpt_tableau__student_course_grades`, `bridge_course_section_teachers`,
  `fct_family_communications`, `base_powerschool__sections`,
  `int_powerschool__ps_adaadm_daily_ctod`, `int_students__contacts`.

## Design decisions

### Producer macro: rename, optional arg

Rename `extract_code_location` to `extract_source_project`, with an **optional**
relation argument that defaults to the unqualified form:

```sql
{% macro extract_source_project(relation="") %}
    regexp_extract(
        {% if relation %}{{ relation }}.{% endif %}_dbt_source_relation,
        r'(kipp\w+)_'
    )
{% endmacro %}
```

- Called **with** an alias (`extract_source_project("wc")`) it renders the
  qualified form — defensive in a `SELECT` that joins several relations, and
  robust if a producer ever has two `_dbt_source_relation` columns in scope.
- Called **with no arg** (`extract_source_project()`) it renders the unqualified
  `regexp_extract(_dbt_source_relation, ...)`. This is the **exact string** that
  `stg_powerschool__courses`, `stg_powerschool__students`,
  `stg_powerschool__studentcorefields`, `stg_powerschool__s_nj_stu_x`,
  `stg_titan__person_data`, and `int_edplan__njsmart_powerschool_union` already
  use inline today — all bare `select *` + AM04 views, all green in CI. So it is
  AM04-clean and unit-test-safe (the old table qualifier was the only reason
  inline was ever preferred; omitting it in `select *` / unit-tested views
  reproduces the proven-safe form).

The qualifier existed **only** because the macro was also used in join clauses,
where `a.` and `b.` must be disambiguated. This refactor deletes every join
usage, so the arg reverts to a defensive, optional convenience.

Apply the macro to every `union_relations` view whose warehouse schema prefix
**is** the home region (~118 views): backfill those missing the column, and
convert the 9 inline copies to the macro. Contracted producers (`staging/`,
`marts/`) also add the new column to their `properties.yml`.

### Region carve-out: crosswalk-resolved sources

A minority of union sources cannot derive region from a regex on
`_dbt_source_relation`, because the raw relation is wrong or meaningless for
region. These resolve `_dbt_source_project` from
`int_people__location_crosswalk.location_dagster_code_location` instead, and the
macro must **not** be forced onto them:

- **iReady** (`int_iready__*`) — Newark, Camden, and Paterson all land in the
  shared `kippnj_iready` schema, so the regex yields `kippnj`, not the home
  region.
- **renlearn** (`stg_renlearn__star`) — shared `kippnj_renlearn` schema.
- **amplify mClass** (`int_amplify__mclass__*`) — the union column encodes SFTP
  vs API delivery method (and is renamed `_dbt_source_relation_2`), not region.

These stay crosswalk-resolved and are normalized to one crosswalk-direct pattern
(`location_dagster_code_location as _dbt_source_project`). Several of the 63
backfill-pending views fall here (the other iReady models, the amplify SFTP
staging models); they need a crosswalk join added, not a macro call. The
CLAUDE.md rule documents this exception explicitly.

### Consumer joins

Replace every `union_dataset_join_clause(a, b)` call with
`a._dbt_source_project = b._dbt_source_project`, threading `_dbt_source_project`
through the consumer's own CTEs so both aliases expose it. The two non-producer
`extract_code_location` sites become plain column references:

- `int_students__fldoe_fte` — `extract_code_location("att") = 'kippmiami'`
  becomes `att._dbt_source_project = 'kippmiami'`.
- `qa_edplan__powerschool_mismatch` —
  `extract_code_location(table="s") as code_location` becomes
  `s._dbt_source_project as code_location`.

### Cleanup

- Delete `union_dataset_join_clause` from `macros/utils.sql` (only after 0 call
  sites remain).
- **Reverse** the `kipptaf/CLAUDE.md` guidance: the current "prefer inline
  `regexp_extract` in `select *` / unit-test views" rule becomes "always use
  `extract_source_project()` on `union_relations` views, except the
  crosswalk-resolved sources named above." Update the
  `union_dataset_join_clause (critical)` section and the `marts/CLAUDE.md`
  hash-and-join note.

### Enforcement

Convention only — apply the macro everywhere (outside the carve-out) and
document it as the rule. No automated CI guard. A source-level guard cannot
distinguish macro from inline anyway (they compile identically), and a
data-level guard would only assert the column exists, not how it was derived.

## The invariant (why every swap is safe)

`union_dataset_join_clause(a, b)` expands to:

```sql
regexp_extract(a._dbt_source_relation, r'(kipp\w+)_')
= regexp_extract(b._dbt_source_relation, r'(kipp\w+)_')
```

`_dbt_source_project` is defined as
`regexp_extract(_dbt_source_relation, r'(kipp\w+)_')` (or, for carve-out
sources, the crosswalk equivalent — which is what the old macro also resolved to
for those rows). So `a._dbt_source_project = b._dbt_source_project` is
byte-identical in result — **provided both `a` and `b` expose the column.** That
single prerequisite makes each swap a provably behavior-preserving refactor,
verifiable by row equality rather than judgment.

## Batch sequence

Dependency-layer first (producers before the consumers that join on them), then
by directory. Each lettered sub-step is its own PR — 1a standalone, 1b split per
source group, 1c standalone, each `2x` per directory, 3 standalone — with the
producer-gate ordering enforced across them (1 before 2, 2 before 3). The
implementation plan enumerates the exact file list per PR.

```text
Batch 1 — MACRO RENAME + PRODUCER BACKFILL (kipptaf-only, self-contained)
  1a Rename extract_code_location -> extract_source_project (optional relation arg,
     default unqualified) across the macro def + all existing call sites.
     Front-loaded and behavior-preserving, so every later batch writes the final name.
  1b Regex-producers (schema prefix = home region, ~118 views): add extract_source_project()
     to those still missing the column; convert the 9 inline copies to the macro.
     Grouped by source: powerschool (~30) / deanslist / illuminate / pearson / amplify(api) /
     overgrad / fldoe / titan / adp / zendesk.
  1c Crosswalk carve-out (iReady / renlearn / amplify mClass): resolve _dbt_source_project
     from int_people__location_crosswalk.location_dagster_code_location, normalized to one
     crosswalk-direct pattern. Add the crosswalk join where a backfill-pending model lacks it.
  Contracted producers add the column to properties.yml.

Batch 2 — CONSUMER JOIN SWAPS, by directory (only after Batch 1 lands the columns)
    2a extracts/tableau rpt_ (41 files -> 2-3 sub-PRs: gradebook / assessment+state / attendance+culture+misc)
    2b extracts/tableau/intermediate (gradebook_audit scaffolds)
    2c extracts/google (12)
    2d extracts/deanslist (8) + clever (2) + powerschool (2) + littlesis (1)
    2e non-extract: powerschool/intermediate (5), topline/intermediate (3),
       students/intermediate (3), marts (3), assessments/intermediate (1),
       kippadb/intermediate (1), reporting/intermediate (1), google/sheets (1)
    2f qa + tests + analyses (5)
  Each swap threads _dbt_source_project through the consumer's CTEs so aliases resolve.

Batch 3 — MACRO REMOVAL + DOCS (only after 0 union_dataset_join_clause call sites remain)
  - Delete union_dataset_join_clause from utils.sql
  - Reverse kipptaf/CLAUDE.md guidance (incl. the carve-out exception); update marts/CLAUDE.md
  - Reconcile the 7 half-migrated files for stragglers
```

Note: some intermediates are **both** a producer to fix in Batch 1 and a
consumer to swap in Batch 2 (e.g. `int_powerschool__gpprogress_grades`).
Multi-level chains (`stg_powerschool__gpnode` to
`int_powerschool__gpprogress_grades` to `int_topline__gpa_term_weekly`) thread
the column through each level; the implementation plan sequences these
producer-first.

## Verification per batch

Because each swap is algebraically identical, verification targets equality, not
plausibility:

1. Dev `--defer` build of each touched model against a fresh prod baseline;
   compare row counts and distinct-key counts. Watch for stale-dev-shadow false
   positives (a stale dev parent produces phantom row/relationships deltas — see
   `src/dbt/CLAUDE.md`).
1. CI `state:modified+` relationships and uniqueness tests stay green.
1. Before each swap, grep the compiled SQL to confirm both aliases expose
   `_dbt_source_project` (the invariant prerequisite).
1. `dbt parse` / `compile` to confirm the swapped SQL renders.
1. For carve-out sources, spot-check that `_dbt_source_project` holds the home
   region (e.g. a Newark iReady row reads `kippnewark`, not `kippnj`).

## Risks and gotchas

- **Producer gate.** Swapping a consumer before its producer carries the column
  fails with `Name _dbt_source_project not found`. Strict Batch 1 -> Batch 2
  ordering prevents this.
- **Carve-out mis-derivation.** Mechanically adding `extract_source_project()`
  to a shared-schema source (iReady / renlearn) assigns every NJ row `kippnj`
  and silently breaks region attribution. Batch 1c must use the crosswalk for
  these.
- **Multi-level chains.** The column must be threaded through every intermediate
  level, not just the leaf producer.
- **Contracted models.** Adding the column to a `staging/`, `marts/`, or `rpt_`
  model requires the matching `properties.yml` column entry, or contract
  enforcement fails at build.
- **Half-migrated files.** The 7 files carrying both idioms must be reconciled,
  not double-processed.
- **Refactor regex sweeps include `*.md`.** The rename and removal touch
  `kipptaf/CLAUDE.md`, `marts/CLAUDE.md`, and this spec — include Markdown in
  any identifier sweep.

## Out of scope

- Removing or renaming `_dbt_source_relation` itself — it stays; models may
  still select or carry it.
- The `extract_region` macro (line 9 of `utils.sql`) — it reads
  `_dbt_source_project` to derive region and is unaffected.
- Any automated enforcement mechanism (decided: convention only).

## Acceptance criteria

- [ ] Every `union_relations` view projects `_dbt_source_project`: the ~118
      schema-prefix-is-region views via `extract_source_project()` (0 inline
      `regexp_extract(_dbt_source_relation, ...)` producer copies remain); the
      carve-out sources via the crosswalk.
- [ ] 0 `union_dataset_join_clause` call sites remain; the macro is deleted from
      `macros/utils.sql`.
- [ ] `extract_code_location` is renamed to `extract_source_project` (optional
      arg); the 2 non-producer sites are plain column refs.
- [ ] `kipptaf/CLAUDE.md` and `marts/CLAUDE.md` reflect the macro-everywhere
      rule and the crosswalk carve-out.
- [ ] All cross-mart relationships and uniqueness tests stay at their current
      severity with 0 new failures; CI green.
