# CLAUDE.md — `dbt/pearson/`

Source-system staging project for **Pearson** New Jersey state assessments —
PARCC, NJSLA, NJSLA Science, and NJGPA — plus supplementary student-list and
test-update feeds. Staging-only. Consumers:
`grep -l 'local: ../pearson' src/dbt/*/packages.yml`.

`kipppaterson` enables only the NJSLA models — see `dbt/kipppaterson/CLAUDE.md`.
