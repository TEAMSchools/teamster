# CLAUDE.md — `dbt/amplify/`

Source-system staging project for **Amplify** reading assessments. Covers two
product lines with different ingestion paths, split into method subfolders:

- `dds/` — Amplify DDS (SFTP file drops)
- `mclass/api/` — mClass API data
- `mclass/sftp/` — mClass SFTP file drops

`dds` and `mclass/api` can be independently enabled/disabled per school in the
consuming project's `dbt_project.yml` (e.g. `kipppaterson` disables both).

`kipptaf` keeps its own native amplify models rather than importing this
package.
