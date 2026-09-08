# CLAUDE.md — `dbt/edplan/`

Source-system staging project for **EdPlan** (special education / IEP management
platform). Consumers: `grep -l 'local: ../edplan' src/dbt/*/packages.yml`.

`stg_edplan__njsmart_powerschool_archive` is disabled in NJ district projects
(enabled only in `kipptaf` if needed).

`int_edplan__njsmart_powerschool_union` unions hot staging with a one-time
NJSMART archive table that exists only in `kippnewark_edplan` and
`kippcamden_edplan`. A region onboarded after that load has no archive table, so
it sets `edplan_has_archive: false` in its `dbt_project.yml` to drop that leg
(currently `kipppaterson`).
