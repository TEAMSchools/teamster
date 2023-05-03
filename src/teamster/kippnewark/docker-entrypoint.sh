#!/bin/sh

# start powerschool ssh tunnel
sshpass -p "${KIPPNEWARK_PS_SSH_PASSWORD}" \
  ssh "${KIPPNEWARK_PS_SSH_USERNAME}"@"${KIPPNEWARK_PS_SSH_HOST}" \
  -p "${KIPPNEWARK_PS_SSH_PORT}" \
  -L 1521:"${KIPPNEWARK_PS_SSH_REMOTE_BIND_HOST}":1521 \
  -o StrictHostKeyChecking=no -4fN

# Run the passed-in Dagster CMD
exec "$@"
