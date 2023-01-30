#!/bin/bash

sshpass -p "${PS_SSH_PASSWORD}" \
  ssh \
  -o StrictHostKeyChecking=no \
  -p "${PS_SSH_PORT}" \
  -L 1521:"${PS_SSH_REMOTE_BIND_HOST}":1521 \
  "${PS_SSH_USERNAME}"@"${PS_SSH_HOST}" -N
