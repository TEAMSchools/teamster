# CLAUDE.md — `dbt/kippnewark/`

District-specific dbt project for **KIPP New Jersey - Newark** schools. Combines
local PowerSchool staging with cross-project references to produce school-level
extracts.

## Model Structure

```text
models/
  powerschool/   # district-specific PowerSchool staging (refs powerschool package)
    sis/staging/
  edplan/        # refs edplan package
  extracts/
    powerschool/ # PowerSchool autocomm extracts (teachers, students IEP)
```
