# CLAUDE.md — `dbt/cambium/`

Source-system staging project for **Cambium TIDE** New Jersey state assessments.
New Jersey moved NJGPA, NJSLA and NJSLA Science score reporting from Pearson
Access Next to Cambium TIDE with the Spring 2026 administration.

Paterson imports the package for NJSLA only and disables `stg_cambium__njgpa`
and its source — Paterson does not sit for NJGPA.

NJSLA and NJSLA Science arrive in ONE file (the District Summative Record File),
so a silent column change in `stg_cambium__njsla` drops three assessments at
once (ELA, Mathematics, Science). The Algebra I, Algebra II and Geometry
end-of-course tests come in a second file with the same header, but a re-issued
NJSLA file can bundle them too. So both files go in the `cambium/njsla`
Couchdrop folder, one Dagster folder asset (`njsla`) reads them, and
`stg_cambium__njsla` keeps the copy of each `student_test_uuid` from the most
recently modified file.

Column names are snake_case because Cambium ships spaced CSV headers, where
Pearson shipped camel case. Only 11 of 225 column names overlap with
`stg_pearson__njgpa`; the two are unrelated schemas over the same assessment.
The `stg_cambium__*` models keep Cambium's names: they cast types, apply the
summative and attempted filter, and derive `test_date`, nothing more. The
mapping into the shared NJ-assessment shape (neutral names plus the aligned
reporting columns) is `int_cambium__all_assessments`, which each district builds
and kipptaf reads via `source()`. The `cambium_state_assessment_relations` var
lists the staging models it unions; a district that disables one overrides the
var (see kipppaterson). A column kipptaf needs from Cambium must first be added
here, and reaches kipptaf only after the district prod rebuild.
