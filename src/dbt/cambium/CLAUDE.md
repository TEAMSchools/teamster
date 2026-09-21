# CLAUDE.md — `dbt/cambium/`

Source-system staging project for **Cambium TIDE** New Jersey state assessments.
New Jersey moved NJGPA, NJSLA and NJSLA Science score reporting from Pearson
Access Next to Cambium TIDE with the Spring 2026 administration. Staging-only.
Consumers: `grep -l 'local: ../cambium' src/dbt/*/packages.yml`.

Paterson imports the package for NJSLA only and disables `stg_cambium__njgpa`
plus its source — Paterson does not sit for NJGPA.

NJSLA and NJSLA Science arrive in ONE file (the District Summative Record File),
split into two assessments by the `assessment_name` derivation in
`stg_cambium__njsla`. A silent column change there drops three assessments at
once (ELA, Mathematics, Science).

Column names are snake_case because Cambium ships spaced CSV headers, where
Pearson shipped camel case. Only 11 of 225 column names overlap with
`stg_pearson__njgpa`; the two are unrelated schemas over the same assessment.
Each `stg_cambium__*` model maps them into the shared NJ-assessment column shape
(Pearson names plus the aligned reporting columns) so kipptaf unions the two
vendors as passthroughs. The union point is kipptaf's own
`int_pearson__all_assessments`, which lists these models beside the districts'
aligned pearson output — keep the shape in step with its `include` list, not
with the pearson package model of the same name.
