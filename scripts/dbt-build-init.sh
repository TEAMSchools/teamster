#!/bin/bash

uv run scripts/dbt-sxs.py kippcamden
uv run dbt build --full-refresh --project-dir=src/dbt/kippcamden/

uv run scripts/dbt-sxs.py kippmiami
uv run dbt build --full-refresh --project-dir=src/dbt/kippmiami/

uv run scripts/dbt-sxs.py kippnewark
uv run dbt build --full-refresh --project-dir=src/dbt/kippnewark/

uv run scripts/dbt-sxs.py kipppaterson
uv run dbt build --full-refresh --project-dir=src/dbt/kipppaterson/

uv run scripts/dbt-sxs.py kipptaf
uv run dbt build --full-refresh --project-dir=src/dbt/kipptaf/
