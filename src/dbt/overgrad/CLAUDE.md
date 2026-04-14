# CLAUDE.md — `dbt/overgrad/`

Source-system staging project for **Overgrad** (college counseling and
application tracking platform). Produces staging and intermediate models.

## Model Structure

```text
models/
  staging/
  intermediate/
  sources.yml
```

## Cross-Project Usage

Referenced by `kippnewark`, `kippcamden`, and `kipptaf`. District projects
disable `stg_overgrad__followings` and `stg_overgrad__schools` (not available
for all schools).
