#!/bin/bash

# inject 1Password secrets
source ./.devcontainer/scripts/inject-secrets.sh

uv self update # reliable enough to not pin a version
uv tool upgrade --all
uv sync --frozen
