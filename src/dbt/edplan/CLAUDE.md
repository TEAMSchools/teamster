# CLAUDE.md — `dbt/edplan/`

Source-system staging project for **EdPlan** (special education / IEP management
platform). Consumers: `grep -l 'local: ../edplan' src/dbt/*/packages.yml`.

`stg_edplan__njsmart_powerschool_archive` is disabled in NJ district projects
(enabled only in `kipptaf` if needed).
