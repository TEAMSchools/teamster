#!/bin/bash

dagster-cloud deployment settings set-from-file ./.dagster/deployment-settings.yaml

envsubst <./.dagster/alerts.yaml.tmpl >./.dagster/alerts.yaml
dagster-cloud deployment alert-policies sync -a ./.dagster/alerts.yaml
