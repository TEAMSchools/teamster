#!/bin/bash

branch=$(git branch --show-current)

cp env/"${branch^^}".env env/.env
