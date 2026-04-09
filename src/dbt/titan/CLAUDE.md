# CLAUDE.md — `dbt/titan/`

Source-system staging project for **Titan K12** (school meals / nutrition
management platform). Staging-only project.

## Model Structure

```text
models/
  staging/
  sources.yml
```

## Cross-Project Usage

Referenced by `kippnewark`, `kippcamden`, and `kipptaf`. The model
`stg_titan__income_form_data` is disabled in NJ district projects.
