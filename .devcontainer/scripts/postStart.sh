#!/bin/bash

# inject 1Password secrets into .env
op inject -f --in-file=.devcontainer/tpl/.env.tpl --out-file=env/.env

# update uv
uv self update

# update trunk
trunk upgrade -y --no-progress
