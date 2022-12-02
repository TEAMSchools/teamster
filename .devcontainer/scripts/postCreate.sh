#!/bin/bash

# update apt packages
sudo apt-get -qq -y update --no-install-recommends &&
	sudo apt-get -qq -y install --no-install-recommends bash-completion &&
	sudo apt-get -qq -y upgrade --no-install-recommends &&
	sudo apt-get -qq autoremove -y &&
	sudo apt-get -qq clean -y

# update pip
python -m pip install --no-cache-dir --upgrade pip

# install Trunk
curl https://get.trunk.io -fsSL | bash -s -- -y

# install pdm dependencies
pdm install --no-self

# commit new files
git add .
git commit -m "Initial PDM commit"
git push
