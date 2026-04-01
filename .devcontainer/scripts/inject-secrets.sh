#!/bin/bash
set -euo pipefail

# restrict permissions on output files
umask 077

# create a private temp directory instead of using shared /tmp
TMPDIR=$(mktemp -d)
chmod 700 "${TMPDIR}"

# cleanup on failure, interruption, or exit
cleanup() {
  rm -rf "${TMPDIR}"
}
trap cleanup ERR EXIT INT TERM HUP

tpl_file=".devcontainer/tpl/.env.tpl"
if [[ -L ${tpl_file} ]]; then
  echo "❌ ${tpl_file} is a symlink — aborting" >&2
  exit 1
fi

# validate secret-volume directory permissions
if [[ -d /etc/secret-volume ]]; then
  perms=$(stat -c '%a' /etc/secret-volume)
  if [[ ${perms} != "700" && ${perms} != "750" && ${perms} != "755" && ${perms} != "777" ]]; then
    echo "❌ /etc/secret-volume has unexpected permissions: ${perms}" >&2
    exit 1
  fi
fi

# inject 1Password secrets into .env with empty-output check
TMP_ENV="${TMPDIR}/.env.tmp"
op inject -f --in-file=.devcontainer/tpl/.env.tpl --out-file="${TMP_ENV}"
if [[ ! -s ${TMP_ENV} ]]; then
  echo "❌ op inject produced empty output for .env" >&2
  exit 1
fi
install -m 600 "${TMP_ENV}" /etc/secret-volume/.env

# download file-based secrets (stored as 1Password documents)
download_doc() {
  local vault="$1" item="$2" filename="$3"
  local tmp_doc="${TMPDIR}/${filename}"
  op read "op://${vault}/${item}/${filename}" --out-file "${tmp_doc}"
  if [[ ! -s ${tmp_doc} ]]; then
    echo "❌ op read produced empty output for ${filename}" >&2
    exit 1
  fi
  install -m 600 "${tmp_doc}" "/etc/secret-volume/${filename}"
}

download_doc "Data Team" "ADP Workforce Now API" "adp_wfn_api.cer"
download_doc "Data Team" "ADP Workforce Now API" "adp_wfn_api.key"
download_doc "Data Team" "TEAMster 1Password Credentials File" "1password-credentials.json"
download_doc "Data Team" "DeansList API" "deanslist_api_key_map.yaml"
download_doc "Data Team" "Egencia SFTP" "id_rsa_egencia"
