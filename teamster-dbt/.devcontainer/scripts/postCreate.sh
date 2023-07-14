#!/bin/bash

# update apt packages
sudo apt-get -qq -y update --no-install-recommends &&
	sudo apt-get -qq -y install --no-install-recommends bash-completion &&
	sudo apt-get -qq -y upgrade --no-install-recommends &&
	sudo apt-get -qq autoremove -y &&
	sudo apt-get -qq clean -y

# set up dbt env
sudo mkdir -p /etc/secret-volume
echo "${DBT_USER_CREDS}" | sudo tee /etc/secret-volume/dbt_user_creds_json >/dev/null
