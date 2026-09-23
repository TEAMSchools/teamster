# Procedure: Add a new region

1. Ensure the **KIPP NJ Gradebook Audit** PS plugin is deployed to the new
   region's PowerSchool instance and the `U_EXPECTATIONS` table is populated.
   Plugin source and update instructions:
   [TEAMSchools/ps-plugins](https://github.com/TEAMSchools/ps-plugins)
2. Wire the ingestion and the union — four files, in this order (Paterson's
   rollout in #4879 is the worked example):
   - add `u_expectations` to
     `src/teamster/code_locations/<district>/powerschool/sis/dlt/config/assets.yaml`
     (`cursor_column: whenmodified`, `intraday: true`, `nightly: false`) and
     bump that district's hardcoded asset counts in `tests/`
   - drop the `stg_powerschool__u_expectations: +enabled: false` entry from
     `src/dbt/<district>/dbt_project.yml`
   - add the `stg_powerschool__u_expectations` source entry to
     `src/dbt/kipptaf/models/powerschool/sources-<district>.yml`
   - add the relation to `union_relations` in
     `src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__u_expectations.sql`
3. **Materialize the dlt asset BEFORE enabling the dbt staging model, and
   confirm the BigQuery table exists.** dlt creates no table at all for the
   first load of a source table that is empty, and the newly enabled staging
   model then fails on a missing relation — which cascades into the kipptaf
   union and takes the whole gradebook audit down, not just the new region. The
   plugin being installed is not sufficient; the table needs at least one row.
4. Verify `int_powerschool__u_expectations_qtd_unpivot` returns rows for the new
   region.
5. No flag sheet changes needed — the flag columns in
   `rpt_tableau__gradebook_audit` apply to all regions. The only exclusions,
   applied in `category_join`'s `WHERE` clause (and matched in
   `int_extracts__gradebook_audit_student_flags`'s own filters, which both
   reports inherit), are `_dbt_source_project != 'kippmiami'`,
   `school_level_alt != 'ES'` (MS/HS only), `exclude_from_gpa = 0`, and
   `course_number != 'SEM22106G1'` (KIPP Newark Lab advisory). Confirm sections
   for the new region appear in `rpt_tableau__gradebook_audit`.
