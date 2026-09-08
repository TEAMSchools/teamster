# CLAUDE.md — `dbt/pearson/`

Source-system staging project for **Pearson** New Jersey state assessments —
PARCC, NJSLA, NJSLA Science, and NJGPA — plus supplementary student-list and
test-update feeds. Staging-only. Consumers:
`grep -l 'local: ../pearson' src/dbt/*/packages.yml`.

`kipppaterson` enables only the NJSLA models — see `dbt/kipppaterson/CLAUDE.md`.

`int_pearson__all_assessments` unions the staging models named in the
`pearson_state_assessment_relations` var and adds the aligned reporting columns.
A district overrides the var to drop disabled models or substitute its own
ID-remapped `int_pearson__*` models (kipppaterson does both).
