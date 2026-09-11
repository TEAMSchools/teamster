# CLAUDE.md — `dbt/renlearn/`

Source-system staging project for **Renaissance Learning** (Accelerated Reader
and STAR assessments). Staging-only. Consumers:
`grep -l 'local: ../renlearn' src/dbt/*/packages.yml`.

- `kippmiami` is the only consumer. Newark retired STAR (#5101): Renaissance
  shipped 0-byte `SM.csv` / `SR.csv` for the NJ region, so that leg only ever
  produced all-null rows.
