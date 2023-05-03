#!/bin/sh

# start powerschool ssh tunnel
sshpass -p "${KIPPCAMDEN_PS_SSH_PASSWORD}" \
  ssh "${KIPPCAMDEN_PS_SSH_USERNAME}"@"${KIPPCAMDEN_PS_SSH_HOST}" \
  -p "${KIPPCAMDEN_PS_SSH_PORT}" \
  -L 1521:"${KIPPCAMDEN_PS_SSH_REMOTE_BIND_HOST}":1521 \
  -o StrictHostKeyChecking=no -4fN

# Run the passed-in Dagster CMD
exec "$@"
