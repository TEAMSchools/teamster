#!/bin/bash

# update apt packages
sudo apt-get -qq -y update --no-install-recommends &&
	sudo apt-get -qq -y install --no-install-recommends bash-completion &&
	sudo apt-get -qq -y upgrade --no-install-recommends &&
	sudo apt-get -qq autoremove -y &&
	sudo apt-get -qq clean -y

# install Trunk
curl https://get.trunk.io -fsSL | bash -s -- -y
