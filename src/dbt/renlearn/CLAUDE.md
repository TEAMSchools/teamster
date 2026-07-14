# CLAUDE.md — `dbt/renlearn/`

Source-system staging project for **Renaissance Learning** (Accelerated Reader
and STAR assessments). Staging-only. Consumers:
`grep -l 'local: ../renlearn' src/dbt/*/packages.yml`.

- `kippnewark` targets its dataset via the `renlearn_schema` var
  (`kippnj_renlearn`) and disables several models (Accelerated Reader, STAR
  fast/dashboard/skill).
