# CLAUDE.md — `dbt/pearson/`

Source-system staging project for **Pearson** New Jersey state assessments —
PARCC, NJSLA, NJSLA Science, and NJGPA — plus supplementary student-list and
test-update feeds. Staging-only project.

## Model Structure

```text
models/
  staging/
  sources-external.yml
```

## Cross-Project Usage

Referenced as a dbt package by `kippnewark`, `kippcamden`, and `kipppaterson`;
`kipptaf` consumes the resulting tables via `source()`.
