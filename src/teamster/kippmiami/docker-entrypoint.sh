#!/bin/sh

# start powerschool ssh tunnel
sshpass -p "${KIPPMIAMI_PS_SSH_PASSWORD}" \
  ssh "${KIPPMIAMI_PS_SSH_USERNAME}"@"${KIPPMIAMI_PS_SSH_HOST}" \
  -p "${KIPPMIAMI_PS_SSH_PORT}" \
  -L 1521:"${KIPPMIAMI_PS_SSH_REMOTE_BIND_HOST}":1521 \
  -o StrictHostKeyChecking=no -4fN

# Run the passed-in Dagster CMD
exec "$@"
