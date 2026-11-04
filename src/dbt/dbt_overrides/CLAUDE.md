# CLAUDE.md — `dbt/dbt_overrides/`

Macro-only package holding patched copies of dbt built-ins. Today it holds one:
the BigQuery `test` materialization in `macros/materialization_test.sql`. It
drops a stored-failure relation only when the relation type changes, so two runs
storing the same test's failures never leave a moment with no relation.

dbt 1.12 ignores a package's override of a built-in materialization
(`require_explicit_package_overrides_for_builtin_materializations`). Every
`kipp*` project therefore carries a root stub,
`macros/materialization_test.sql`, that returns
`dbt_overrides.materialization_test_bigquery()`. dbt resolves the test
materialization by the root project, so tests from source packages use the stub
too.

`tests/test_dbt_overrides.py` fails when a dbt upgrade changes the built-in
materialization. To re-sync, copy the new upstream file the test names, apply
its `PATCHES`, keep this file's header lines, and re-run the test. If a patch
site moved, update `PATCHES` to match the new upstream text.
