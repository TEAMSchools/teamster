# CLAUDE.md — `dbt/cambium/`

Source-system staging project for **Cambium TIDE** New Jersey state assessments.
New Jersey moved NJGPA score reporting from Pearson Access Next to Cambium TIDE
with the Spring 2026 administration; NJSLA and NJSLA Science are still on
Pearson. Staging-only. Consumers:
`grep -l 'local: ../cambium' src/dbt/*/packages.yml`.

Only `kippnewark` and `kippcamden` import this package — Paterson does not sit
for NJGPA and has `stg_pearson__njgpa` disabled.

Column names are snake_case because Cambium ships spaced CSV headers, where
Pearson shipped camel case. Only 11 of 225 column names overlap with
`stg_pearson__njgpa`; the two are unrelated schemas over the same assessment.
Alignment into the shared NJ-assessment column shape happens in kipptaf's
`stg_cambium__njgpa`, not here.
