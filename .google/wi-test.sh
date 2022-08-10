#!/bin/bash

# Create the Pod:
kubectl apply -f ./.google/wi-test.yaml

# Open an interactive session in the Pod:
kubectl exec -it workload-identity-test --namespace dagster-cloud -- /bin/bash

# If the service accounts are correctly configured, the IAM service account email address
# is listed as the active (and only) identity. This demonstrates that by default, the Pod
# acts as the IAM service account's authority when calling Google Cloud APIs.
curl -H "Metadata-Flavor: Google" \
	http://169.254.169.254/computeMetadata/v1/instance/service-accounts/

# Check that public IP matches Cloud NAT static IP (https://console.cloud.google.com/networking/addresses/list)
curl ifconfig.me/all
