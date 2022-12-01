#!/bin/bash

branch=$(git branch --show-current)

cp --remove-destination env/"${branch^^}".env env/.env
