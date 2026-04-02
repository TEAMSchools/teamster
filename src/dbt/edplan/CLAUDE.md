# CLAUDE.md — `dbt/edplan/`

Source-system staging project for **EdPlan** (special education / IEP management
platform). Produces staging and intermediate models consumed by NJ district
projects and `kipptaf`.

## Model Structure

```text
models/
  staging/
  intermediate/
  sources.yml
  sources-archive.yml   # legacy archived sources
```

## Cross-Project Usage

Referenced by `kippnewark`, `kippcamden`, and `kipptaf`. The model
`stg_edplan__njsmart_powerschool_archive` is disabled in NJ district projects
(enabled only in `kipptaf` if needed).
