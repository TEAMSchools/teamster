# CLAUDE.md — `dbt/iready/`

Source-system staging project for **i-Ready** (diagnostic and instructional
platform for reading and math). Consumers:
`grep -l 'local: ../iready' src/dbt/*/packages.yml`.

- `kippnewark` targets its dataset via the `iready_schema` var (`kippnj_iready`)
  and disables `stg_iready__instructional_usage_data`.
