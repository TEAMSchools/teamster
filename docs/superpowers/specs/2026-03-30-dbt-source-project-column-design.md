# Design: Replace `union_dataset_join_clause` with `_dbt_source_project` Column

**Issue**: [#3142](https://github.com/TEAMSchools/teamster/issues/3142)
**Date**: 2026-03-30 **Status**: Approved

## Problem

Cross-district union models in kipptaf carry a `_dbt_source_relation` column
(added by `dbt_utils.union_relations`), but its value includes the full schema +
table name — making direct joins between two union-derived tables unsafe. The
current solution is the `union_dataset_join_clause` macro, which calls
`extract_code_location` to run
`regexp_extract(_dbt_source_relation, r'(kipp\w+)_')` on both sides of every
join. This regex executes at query time on every join — 268 usages across 92
downstream files.

## Solution

Extract the source project once at the union model level as a materialized
column (`_dbt_source_project`), then join on it directly downstream.

### Approach: Per-model column addition with centralized extraction macro

1. **Rename `extract_code_location` to `extract_source_project`** in
   `macros/utils.sql`. Same regex logic, clearer name.

2. **Add `_dbt_source_project` to ~73 cross-district union models.** Wrap in a
   CTE if not already wrapped, then select the new column:

   ```sql
   with
       union_relations as (
           {{ dbt_utils.union_relations(relations=[...]) }}
       )

   select
       *,
       {{ extract_source_project("union_relations") }}
           as _dbt_source_project,
   from union_relations
   ```

   For models already wrapped in a CTE, add the column to whichever CTE/select
   first exposes the union output.

3. **Update properties YAML for contract-enforced models** — add
   `_dbt_source_project` with `data_type: string`.

4. **Replace all 268 macro usages across 92 downstream files.** Each instance
   of:

   ```sql
   and {{ union_dataset_join_clause(left_alias="a", right_alias="b") }}
   ```

   becomes:

   ```sql
   and a._dbt_source_project = b._dbt_source_project
   ```

5. **Remove `union_dataset_join_clause` macro** from `macros/utils.sql`.

6. **Update `kipptaf/CLAUDE.md`** — replace the `union_dataset_join_clause`
   section with documentation for the `_dbt_source_project` column and
   `extract_source_project` macro.

## Scope

### In scope

- Cross-district union models only (sources from multiple `kipp*` datasets).
- All downstream models that use `union_dataset_join_clause`.
- Properties YAML updates for contract-enforced models.
- CLAUDE.md documentation update.

### Out of scope

- Same-source unions (Illuminate repositories, multi-year tables,
  single-district models) — `_dbt_source_project` is not meaningful for these.
- Non-kipptaf dbt projects — the macro and pattern are kipptaf-specific.

## Affected files

| Category                            | Count | Change                                           |
| ----------------------------------- | ----- | ------------------------------------------------ |
| Cross-district union models (SQL)   | ~73   | Add `_dbt_source_project` column                 |
| Properties YAML (contract-enforced) | ~73   | Add column declaration                           |
| Downstream join models              | ~92   | Replace macro with column comparison             |
| `macros/utils.sql`                  | 1     | Rename macro, remove `union_dataset_join_clause` |
| `kipptaf/CLAUDE.md`                 | 1     | Update documentation                             |

## Macro changes

### Before

```sql
{% macro extract_code_location(table) %}
    regexp_extract({{ table }}._dbt_source_relation, r'(kipp\w+)_')
{% endmacro %}

{% macro union_dataset_join_clause(left_alias, right_alias) %}
    {{ extract_code_location(left_alias) }}
    = {{ extract_code_location(right_alias) }}
{% endmacro %}
```

### After

```sql
{% macro extract_source_project(relation) %}
    regexp_extract({{ relation }}._dbt_source_relation, r'(kipp\w+)_')
{% endmacro %}
```

## Developer impact

### What changes for SQL developers

**Joining cross-district tables (the common case):**

Before:

```sql
inner join {{ ref("other_union_model") }} as b
    on a.id = b.id
    and {{ union_dataset_join_clause(left_alias="a", right_alias="b") }}
```

After:

```sql
inner join {{ ref("other_union_model") }} as b
    on a.id = b.id
    and a._dbt_source_project = b._dbt_source_project
```

No macro import, no Jinja — just a plain column comparison.

**Creating a new cross-district union model:**

Add `_dbt_source_project` using the centralized macro:

```sql
select
    *,
    {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
```

Add to properties YAML (contract-enforced models):

```yaml
- name: _dbt_source_project
  data_type: string
```

**Extracting a human-readable region label:**

The existing pattern
`initcap(regexp_extract(s._dbt_source_relation, r'kipp(\w+)_'))` still works but
can now be derived from `_dbt_source_project` with
`initcap(regexp_extract(s._dbt_source_project, r'kipp(\w+)'))` — one fewer regex
group since the trailing `_` is already stripped.

**BigQuery UDF `functions.region_join()`:**

This UDF is the scalar equivalent of `union_dataset_join_clause()` for use
outside dbt (Cube semantic layer, ad-hoc queries). It currently operates on
`_dbt_source_relation`. Post-refactor, queries can use
`a._dbt_source_project = b._dbt_source_project` directly instead of calling the
UDF. The UDF should be deprecated — removal is a separate task since it requires
coordinating with Cube model definitions.

### Documentation deliverables

- **`docs/reference/dbt-conventions.md`** — update the
  `union_dataset_join_clause()` section (lines 43-59) to document
  `_dbt_source_project` and `extract_source_project`. Update the
  `functions.region_join()` row in the BigQuery scalar functions table to note
  deprecation in favor of `_dbt_source_project`.
- **`src/dbt/kipptaf/CLAUDE.md`** — replace the `union_dataset_join_clause`
  section with `_dbt_source_project` documentation.

## Testing and validation

- `dbt compile` to verify all models parse correctly.
- `dbt build` on a subset of affected models — a powerschool staging model plus
  a downstream extract that joins on `_dbt_source_project` — to confirm data
  correctness.
- Spot-check that `_dbt_source_project` values match expectations (`kippnewark`,
  `kippcamden`, `kippmiami`, `kipppaterson`).
