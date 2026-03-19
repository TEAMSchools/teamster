#!/bin/bash
set -euo pipefail

# restrict permissions on output files
umask 077

# cleanup intermediate files on failure or interruption (#1)
TMP_SECRET=""
cleanup() {
  rm -f env/.env.tmp
  [[ -n ${TMP_SECRET} ]] && rm -f "${TMP_SECRET}"
}
trap cleanup ERR EXIT

# inject 1Password secrets into .env with empty-output check (#6)
op inject -f --in-file=.devcontainer/tpl/.env.tpl --out-file=env/.env.tmp
if [[ ! -s env/.env.tmp ]]; then
  echo "❌ op inject produced empty output for .env" >&2
  exit 1
fi
mv -f env/.env.tmp env/.env

# save secrets to file
for tpl in adp_wfn_api.cer adp_wfn_api.key deanslist_api_key_map_yaml id_rsa_egencia powerschool_ssh_password.txt; do
  # write to a user-writable temp file, then move into place with sudo
  TMP_SECRET=$(mktemp "/tmp/${tpl}.XXXXXX")
  op inject -f --in-file=".devcontainer/tpl/${tpl}.tpl" --out-file="${TMP_SECRET}"

  # verify non-empty output (#6)
  if [[ ! -s ${TMP_SECRET} ]]; then
    echo "❌ op inject produced empty output for ${tpl}" >&2
    rm -f "${TMP_SECRET}"
    exit 1
  fi

  # set explicit permissions and move into place (#3)
  sudo chown root:root "${TMP_SECRET}"
  sudo chmod 600 "${TMP_SECRET}"
  sudo mv -f "${TMP_SECRET}" "/etc/secret-volume/${tpl}"
  TMP_SECRET=""
done
