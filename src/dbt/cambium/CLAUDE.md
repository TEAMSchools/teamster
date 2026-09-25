# CLAUDE.md — `dbt/cambium/`

Source-system staging project for **Cambium TIDE** New Jersey state assessments.
New Jersey moved NJGPA, NJSLA and NJSLA Science score reporting from Pearson
Access Next to Cambium TIDE with the Spring 2026 administration. Staging-only.

Paterson imports the package for NJSLA only and disables `stg_cambium__njgpa`,
`stg_cambium__eoc` and their sources — Paterson does not sit for NJGPA and has
no end-of-course file yet.

NJSLA and NJSLA Science arrive in ONE file (the District Summative Record File),
so a silent column change in `stg_cambium__njsla` drops three assessments at
once (ELA, Mathematics, Science). The Algebra I, Algebra II and Geometry
end-of-course tests come in a second file with the same header,
`stg_cambium__eoc`.

Column names are snake_case because Cambium ships spaced CSV headers, where
Pearson shipped camel case. Only 11 of 225 column names overlap with
`stg_pearson__njgpa`; the two are unrelated schemas over the same assessment.
The `stg_cambium__*` models keep Cambium's names: they cast types, apply the
summative and attempted filter, and derive `test_date`, nothing more. The
mapping into the shared NJ-assessment shape (Pearson names plus the aligned
reporting columns) lives in kipptaf's `int_pearson__all_assessments`. A column
kipptaf needs from Cambium must first be added here.
