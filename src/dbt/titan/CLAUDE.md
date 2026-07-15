# CLAUDE.md — `dbt/titan/`

Source-system staging project for **Titan K12** (school meals / nutrition
management platform). Staging-only. Consumers:
`grep -l 'local: ../titan' src/dbt/*/packages.yml`.

`stg_titan__income_form_data` is disabled in NJ district projects.
