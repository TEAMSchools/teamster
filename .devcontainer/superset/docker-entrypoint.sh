#!/bin/bash
set -eo pipefail

superset db upgrade

superset fab create-admin \
  --username admin \
  --firstname Admin \
  --lastname Admin \
  --email admin@superset.com \
  --password admin 2>/dev/null || true

superset init

exec gunicorn \
  --bind "0.0.0.0:8088" \
  --workers 2 \
  --timeout 120 \
  "superset.app:create_app()"
