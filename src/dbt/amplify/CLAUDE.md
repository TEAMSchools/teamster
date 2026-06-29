# CLAUDE.md — `dbt/amplify/`

Source-system staging project for **Amplify** reading assessments. Covers two
product lines with different ingestion paths:

- `dds/` — Amplify DDS (SFTP file drops)
- `mclass/api/` — mClass API data
- `mclass/sftp/` — mClass SFTP file drops

## Model Structure

```text
models/
  dds/
    staging/
    sources-external.yml
  mclass/
    api/
      staging/
      sources-external.yml
    sftp/
      staging/
      sources-external.yml
```

Both `dds` and `mclass/api` can be independently enabled/disabled per school in
the consuming project's `dbt_project.yml`.

## Cross-Project Usage

Referenced as a dbt package by `kippnewark` and `kipppaterson` (`kipptaf` keeps
its own native amplify models rather than packaging this project). District
projects selectively enable only the Amplify products they use — for example,
`kipppaterson` disables both `dds` and `mclass/api`.
