#!/bin/bash

FLAG=~/.cache/teamster/dbt_dev_datasets_ok

if [[ -f ${FLAG} ]]; then
  exit 0
fi

echo -e "\033[1;36mℹ dbt dev datasets may not be initialized.\033[0m"
echo -e "\033[1;36m  To build:   Ctrl+Shift+P → Tasks: Run Task → dbt: Build Init\033[0m"
echo -e "\033[1;36m  To dismiss: touch ${FLAG}\033[0m"
