#!/bin/bash

# update apt packages
sudo apt-get -qq -y update --no-install-recommends &&
  sudo apt-get -qq -y upgrade --no-install-recommends &&
  sudo apt-get -qq autoremove -y &&
  sudo apt-get -qq clean -y

# update pip
python -m pip install --no-cache-dir --upgrade pip

# update pdm
pdm self update

# update trunk
trunk upgrade -y --no-progress

# save github codespace secrets to .env files
for branch in $(git for-each-ref --format='%(refname:short)' refs/**/kipp*); do
  branch_name=$(basename -- "${branch}")
  branch_name_clean=$(echo "${branch_name^^}" | tr -cd '[:alnum:]')

  if [ -n "${!branch_name_clean}" ]; then
    echo "${!branch_name_clean}" >"./env/${branch_name}.env"
  fi
done
