# CLAUDE.md — `dbt/pearson/`

Source-system project for **Pearson** New Jersey state assessments — PARCC,
NJSLA, NJSLA Science, and NJGPA — plus supplementary student-list and
test-update feeds. Staging plus two intermediates.

Cambium replaced Pearson from Spring 2026. Every district disables the score
models (`stg_pearson__njgpa`, `_njsla`, `_njsla_science`, `_parcc` and
`int_pearson__all_assessments`) and their tests. The last prod
`int_pearson__all_assessments` tables stay in place as frozen history, and
kipptaf reads them. The student-list report models (preliminary scores) and, in
Newark and Camden, `stg_pearson__student_test_update` still build.
