#!/bin/bash

# inject 1Password secrets into .env
op inject -f --in-file=.devcontainer/tpl/.env.tpl --out-file=env/.env

uv self update
uv tool upgrade datamodel-code-generator dagster-dg
