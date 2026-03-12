#!/bin/bash

# inject 1Password secrets into .env
op inject -f --in-file=.devcontainer/tpl/.env.tpl --out-file=env/.env

# save secrets to file
op inject -f --in-file=.devcontainer/tpl/adp_wfn_api.cer.tpl \
  --out-file=env/adp_wfn_api.cer &&
  sudo mv -f env/adp_wfn_api.cer /etc/secret-volume/adp_wfn_api.cer

op inject -f --in-file=.devcontainer/tpl/adp_wfn_api.key.tpl \
  --out-file=env/adp_wfn_api.key &&
  sudo mv -f env/adp_wfn_api.key /etc/secret-volume/adp_wfn_api.key

op inject -f --in-file=.devcontainer/tpl/deanslist_api_key_map_yaml.tpl \
  --out-file=env/deanslist_api_key_map_yaml &&
  sudo mv -f env/deanslist_api_key_map_yaml \
    /etc/secret-volume/deanslist_api_key_map_yaml

op inject -f --in-file=.devcontainer/tpl/id_rsa_egencia.tpl \
  --out-file=env/id_rsa_egencia &&
  sudo mv -f env/id_rsa_egencia /etc/secret-volume/id_rsa_egencia

op inject -f --in-file=.devcontainer/tpl/powerschool_ssh_password.txt.tpl \
  --out-file=env/powerschool_ssh_password.txt &&
  sudo mv -f env/powerschool_ssh_password.txt /etc/secret-volume/powerschool_ssh_password.txt
