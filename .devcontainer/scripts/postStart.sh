#!/bin/bash

# update apt packages
sudo apt-get -qq -y update --no-install-recommends &&
  sudo apt-get -qq -y upgrade --no-install-recommends &&
  sudo apt-get -qq autoremove -y &&
  sudo apt-get -qq clean -y

# update pip
python -m pip install --no-cache-dir --upgrade pip

# update pdm
sudo pdm self update

# update trunk
trunk upgrade -y --no-progress

# save KIPP* github codespace secrets to .env files
for envvar in $(compgen -A variable | grep "^KIPP"); do
  envvar_lower="${envvar,,}"

  if [[ ${envvar_lower} != *"_"* ]]; then
    mkdir -p "./env/${envvar_lower}"
    echo "${!envvar}" >"./env/${envvar_lower}/.env"
  else
    IFS='_' read -ra VAR <<<"${envvar_lower}"
    fpath=""
    for i in "${VAR[@]}"; do
      fpath+="${i}/"
    done

    mkdir -p -- "./env/${fpath%/*}"
    echo "${!envvar}" >"./env/${fpath}rsa-private-key"
  fi

done

mkdir -p ./env/test
echo "${TEST}" >./env/test/.env
