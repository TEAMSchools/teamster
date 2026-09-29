# CLAUDE.md — `dbt/deanslist/`

Source-system staging project for **Deanslist** (behavior management, homework
tracking, and student support platform). Staging is contract-enforced, one model
per Deanslist API endpoint.

Districts disable the staging models (and `src_deanslist__*` sources) for
endpoints they never pull — see `dbt/kipppaterson/CLAUDE.md` for the worked
example and rationale.
