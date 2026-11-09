# CLAUDE.md — `dbt/kippmiami/`

District-specific dbt project for **KIPP Miami** schools (Florida). The only
district project with Florida-specific state data (`fldoe`). Produces
school-level PowerSchool staging and extracts.

## Model Structure

```text
models/
  fldoe/         # Florida Department of Education assessment data
    staging/
```

PowerSchool (pre-Focus SIS) is retired. `kippmiami_powerschool` is a frozen
archive built from `dagster_kippmiami_dlt_powerschool`, the final dlt pull of
Miami's server. Rebuild it whenever a consumer needs a new archive model or
column, or the server's data needs a fix. The loop: turn the Dagster assets on
(`src/teamster/code_locations/kippmiami/CLAUDE.md`), materialize the tables that
need a fresh pull, re-include the package, build, then remove it again.

Restore the recipe from #6012 rather than rewriting it: `063c2a5414` on `main`
is the commit that removed the working config.

```bash
git checkout 063c2a5414^ -- src/dbt/kippmiami/
```

That restores `packages.yml` (`- local: ../powerschool`), the local
`stg_powerschool__u_studentsuserfields` override, and `dbt_project.yml`. The
`dbt_project.yml` has two blocks. The top-level `powerschool:` block turns the
dlt variant on and odbc off, enables every model the package disables by
default, disables the package models Miami never loaded, and carries the
post-hooks: the 8400 Focus prefix on `student_number`, `yearid > 35` deletes
that drop rows past AY2025, and the `stg_powerschool__calendar_day` cut at
`date_value >= '2026-07-01'`. The `kippmiami: powerschool:` block
(`+schema: powerschool`, table, contract) is required, or the local override
builds as a view in the wrong dataset. Run `uv run dbt deps`, build with
`--target dev` first, and compare every table against the archive before the
prod build.

Five archive tables are never rebuilt and stay at their frozen copies:
`int_powerschool__student_contacts` and `_pivot` (the package disables them at
the model level, which a root config cannot override; nothing reads them), and
`stg_powerschool__studenttest`, `stg_powerschool__studenttestscore`, and
`int_powerschool__state_assessments_transfer_scores` (empty on the server, so
dlt created no source table).

`int_fldoe__all_assessments` resolves `student_number` from
`int_focus__students`, not the archive. kipptaf reads the dataset as a BQ-native
source. Do not drop it, `dagster_kippmiami_dlt_powerschool`, or the GCS files.

## Source Packages

`focus` — `focus_schema` points to `dagster_kippmiami_dlt_focus`. Miami does not
use `deanslist`, `edplan`, `overgrad`, `pearson`, `powerschool`, or `titan`.

DeansList was removed in #5110. `kippmiami_deanslist` holds the last build
(2026-07-22), frozen, and kipptaf reads it as a BQ-native source for history. Do
not drop the dataset.
