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

# validate template files are not symlinks
for tpl_file in .devcontainer/tpl/.env.tpl \
  .devcontainer/tpl/adp_wfn_api.cer.tpl \
  .devcontainer/tpl/adp_wfn_api.key.tpl \
  .devcontainer/tpl/deanslist_api_key_map_yaml.tpl \
  .devcontainer/tpl/id_rsa_egencia.tpl \
  .devcontainer/tpl/powerschool_ssh_password.txt.tpl; do
  if [[ -L ${tpl_file} ]]; then
    echo "❌ ${tpl_file} is a symlink — aborting" >&2
    exit 1
  fi
done

# validate secret-volume directory permissions
if [[ -d /etc/secret-volume ]]; then
  perms=$(stat -c '%a' /etc/secret-volume)
  if [[ ${perms} != "700" && ${perms} != "750" && ${perms} != "755" ]]; then
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

# save secrets to file
for tpl in adp_wfn_api.cer adp_wfn_api.key deanslist_api_key_map_yaml id_rsa_egencia powerschool_ssh_password.txt; do
  TMP_SECRET="${TMPDIR}/${tpl}"
  op inject -f --in-file=".devcontainer/tpl/${tpl}.tpl" --out-file="${TMP_SECRET}"

  # verify non-empty output
  if [[ ! -s ${TMP_SECRET} ]]; then
    echo "❌ op inject produced empty output for ${tpl}" >&2
    exit 1
  fi

  # set explicit permissions and move into place
  install -m 600 "${TMP_SECRET}" "/etc/secret-volume/${tpl}"
done
