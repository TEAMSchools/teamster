#!/bin/bash

# inject 1Password secrets into .env
op inject -f --in-file=.devcontainer/tpl/.env.tpl --out-file=env/.env

# update uv
uv self update
uv tool upgrade datamodel-code-generator dagster-dg
uv sync

# update trunk
# trunk-ignore(shellcheck/SC2312)
if [[ $(git symbolic-ref --short HEAD) == "main" ]]; then
  trunk upgrade -y --no-progress
fi
