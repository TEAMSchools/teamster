pdm run env-setup prod

kubectl create secret generic ${INSTANCE_NAME} \
    --save-config \
    --dry-run=client \
    --namespace=dagster-cloud \
    --from-env-file=./env/prod.env \
    --output=yaml \
    | kubectl apply -f -

kubectl create secret generic ${INSTANCE_NAME}-ssh-keys \
    --save-config \
    --dry-run=client \
    --namespace=dagster-cloud \
    --from-file=egencia-privatekey=./secrets/egencia/rsa-private-key \
    --output=yaml \
    | kubectl apply -f -
