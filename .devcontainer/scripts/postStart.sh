#!/bin/bash

# inject 1Password secrets into .env
op inject -f --in-file=.devcontainer/tpl/.env.tpl --out-file=env/.env

# update uv
uv self update
uv tool upgrade datamodel-code-generator

# update trunk
trunk upgrade -y --no-progress
