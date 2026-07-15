# CLAUDE.md — `dbt/overgrad/`

Source-system staging project for **Overgrad** (college counseling and
application tracking platform). Consumers:
`grep -l 'local: ../overgrad' src/dbt/*/packages.yml`.

District projects disable `stg_overgrad__followings` and `stg_overgrad__schools`
(not available for all schools).
