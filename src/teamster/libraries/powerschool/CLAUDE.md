# CLAUDE.md — `teamster/libraries/powerschool/`

- `sis/odbc/` — archived Oracle ODBC code; no code location imports it. Git
  history holds its notes. PowerSchool SIS ingestion lives in
  `libraries/dlt/powerschool/`.
- `sis/sftp/` — SFTP file schemas only; no code location imports them
- `enrollment/` — PowerSchool Enrollment REST API (preserved, not wired into any
  code location)

## Type Annotations

- `oracledb` lacks type stubs — `cursor.description` elements are `FetchInfo` at
  runtime but typed as broad unions. Use `trunk-ignore-begin(pyright)` blocks
  for code that accesses `.lower()` or `.name` on description elements.

## `enrollment/`

Preserved for reuse; no code location imports it. The kipptaf wiring, its
`PS_ENROLLMENT_API_KEY` secret mounts, and tests were removed, so re-wiring
means restoring all three.

**`resources.py`** (`PowerSchoolEnrollmentResource`): REST client for the
PowerSchool Enrollment/Registration API (separate from SIS; handles enrollment
form submissions).

**`assets.py`** (`build_ps_enrollment_submission_records_asset()`): Fetches
submission records for a given enrollment form (dynamic partition by form ID).
