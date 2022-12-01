#!/bin/bash

# update apt packages
sudo apt-get -qq -y update --no-install-recommends &&
  sudo apt-get -qq -y install --no-install-recommends bash-completion &&
  sudo apt-get -qq -y upgrade --no-install-recommends &&
  sudo apt-get -qq autoremove -y &&
  sudo apt-get -qq clean -y

# update pip
pip install --no-cache-dir --upgrade pip

# create gitignore fn
function gi() {
  curl -sL "https://www.toptal.com/developers/gitignore/api/${1}"
}

# install pdm dependencies
pdm install --no-self

# install trunk
curl https://get.trunk.io -fsSL | bash -s -- -y
