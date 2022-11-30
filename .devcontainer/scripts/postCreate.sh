#!/bin/bash

# update apt packages
sudo apt-get -qq -y update --no-install-recommends &&
  sudo apt-get -qq -y install --no-install-recommends bash-completion &&
  sudo apt-get -qq -y upgrade --no-install-recommends &&
  sudo apt-get -qq autoremove -y &&
  sudo apt-get -qq clean -y

# update pip
pip install --no-cache-dir --upgrade pip

# create .gitignore
function gi() {
  curl -sL "https://www.toptal.com/developers/gitignore/api/${1}"
}
gi linux,macos,windows,python >.gitignore

# commit new files
git add .
git commit -m "Initial devcontainer commit"

# install pdm dependencies
pdm install --no-self

curl https://get.trunk.io -fsSL | bash -s -- -y
trunk init --yes-to-all --nocheck-sample >/dev/null
trunk actions enable trunk-announce trunk-check-pre-push trunk-fmt-pre-commit >/dev/null
trunk config share >/dev/null
trunk check --all --fix

# commit new files
git add .
git commit -m "Initial PDM & Trunk commit"
