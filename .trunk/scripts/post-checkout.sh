#!/bin/bash

branch=$(git branch --show-current)

touch env/.env
ln -sf env/"${branch^^}".env env/.env
