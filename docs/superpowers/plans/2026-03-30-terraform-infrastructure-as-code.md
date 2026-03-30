# Terraform Infrastructure as Code Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Codify the Teamster project's GCP infrastructure in Terraform modules
with import blocks for all existing resources, replacing `.gcloud/` and `.k8s/`
shell scripts.

**Architecture:** Module-per-domain structure under `terraform/` at the repo
root. A single root module composes 8 child modules (bootstrap, gke, gcs,
bigquery, artifact_registry, iam, k8s, github). GCS remote state with a
bootstrap module for the state bucket. All existing resources are imported via
declarative `import` blocks.

**Tech Stack:** Terraform >= 1.5.0, Google provider (`hashicorp/google`), Google
Beta provider (`hashicorp/google-beta`), Kubernetes provider
(`hashicorp/kubernetes`), GitHub provider (`integrations/github`), Helm provider
(`hashicorp/helm`)

---

## File Structure

### Root module (`terraform/`)

| File               | Responsibility                                                          |
| ------------------ | ----------------------------------------------------------------------- |
| `versions.tf`      | `required_version` and `required_providers` block                       |
| `backend.tf`       | GCS remote state configuration                                          |
| `providers.tf`     | Provider configurations (google, google-beta, kubernetes, helm, github) |
| `variables.tf`     | Project-level input variables                                           |
| `terraform.tfvars` | Default variable values                                                 |
| `main.tf`          | Module composition — wires all child modules together                   |
| `outputs.tf`       | Key outputs surfaced from child modules                                 |
| `imports.tf`       | All `import` blocks for existing resources                              |

### Child modules (`terraform/modules/<name>/`)

Each module has: `main.tf`, `variables.tf`, `outputs.tf`

| Module               | Resources                                                                                             |
| -------------------- | ----------------------------------------------------------------------------------------------------- |
| `bootstrap/`         | GCS state bucket (separate `versions.tf`, `providers.tf` — local state)                               |
| `gke/`               | GKE Autopilot cluster                                                                                 |
| `gcs/`               | Cloud Storage buckets (6 buckets via `for_each`)                                                      |
| `bigquery/`          | BigQuery datasets (production only) + BigLake connection                                              |
| `artifact_registry/` | Artifact Registry Docker repo                                                                         |
| `iam/`               | Service accounts, Workload Identity Federation, IAM bindings, domain-wide delegation docs             |
| `k8s/`               | Kubernetes namespace, service account, Helm releases (Dagster + 1Password), OnePasswordItem manifests |
| `github/`            | Repository settings, branch protection, Actions secrets/variables                                     |

### Other files

| File                                | Responsibility                        |
| ----------------------------------- | ------------------------------------- |
| `terraform/README.md`               | Pointer to MkDocs infrastructure docs |
| `docs/infrastructure/index.md`      | Architecture overview                 |
| `docs/infrastructure/bootstrap.md`  | Bootstrap and import guide            |
| `docs/infrastructure/operations.md` | Day-to-day Terraform workflow         |
| `docs/infrastructure/modules.md`    | Module reference                      |

---

## Task 1: Scaffold root module and .gitignore

**Files:**

- Create: `terraform/versions.tf`
- Create: `terraform/backend.tf`
- Create: `terraform/providers.tf`
- Create: `terraform/variables.tf`
- Create: `terraform/terraform.tfvars`
- Modify: `.gitignore`

- [ ] **Step 1: Create `terraform/versions.tf`**

```hcl
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.0"
    }
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }
}
```

- [ ] **Step 2: Create `terraform/backend.tf`**

```hcl
terraform {
  backend "gcs" {
    bucket = "teamster-terraform-state"
    prefix = "terraform/state"
  }
}
```

- [ ] **Step 3: Create `terraform/providers.tf`**

```hcl
provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

provider "kubernetes" {
  host                   = "https://${module.gke.cluster_endpoint}"
  token                  = data.google_client_config.default.access_token
  cluster_ca_certificate = base64decode(module.gke.cluster_ca_certificate)
}

provider "helm" {
  kubernetes {
    host                   = "https://${module.gke.cluster_endpoint}"
    token                  = data.google_client_config.default.access_token
    cluster_ca_certificate = base64decode(module.gke.cluster_ca_certificate)
  }
}

provider "github" {
  owner = var.github_org
}

data "google_client_config" "default" {}
```

- [ ] **Step 4: Create `terraform/variables.tf`**

```hcl
variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "project_number" {
  description = "GCP project number"
  type        = string
}

variable "region" {
  description = "Default GCP region"
  type        = string
}

variable "code_locations" {
  description = "Dagster code location names (used for GCS buckets, BigQuery datasets, etc.)"
  type        = list(string)
}

variable "github_org" {
  description = "GitHub organization name"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
}

variable "gke_cluster_name" {
  description = "GKE Autopilot cluster name"
  type        = string
}

variable "bigquery_location" {
  description = "BigQuery dataset and connection location"
  type        = string
}
```

- [ ] **Step 5: Create `terraform/terraform.tfvars`**

```hcl
project_id        = "teamster-332318"
project_number    = "624231820004"
region            = "us-central1"
code_locations    = ["kipptaf", "kippnewark", "kippcamden", "kippmiami", "kipppaterson"]
github_org        = "TEAMSchools"
github_repo       = "teamster"
gke_cluster_name  = "autopilot-cluster-dagster-hybrid-1"
bigquery_location = "us"
```

- [ ] **Step 6: Add Terraform entries to `.gitignore`**

Append to the end of `.gitignore`:

```text

### Terraform ###
**/.terraform/
*.tfstate
*.tfstate.backup
*.tfplan
override.tf
override.tf.json
*_override.tf
*_override.tf.json
```

- [ ] **Step 7: Commit**

```bash
git add terraform/versions.tf terraform/backend.tf terraform/providers.tf \
  terraform/variables.tf terraform/terraform.tfvars
git add -u
git commit -m "feat(terraform): scaffold root module with providers and variables"
```

---

## Task 2: Bootstrap module (state bucket)

**Files:**

- Create: `terraform/modules/bootstrap/versions.tf`
- Create: `terraform/modules/bootstrap/providers.tf`
- Create: `terraform/modules/bootstrap/main.tf`
- Create: `terraform/modules/bootstrap/variables.tf`
- Create: `terraform/modules/bootstrap/outputs.tf`

- [ ] **Step 1: Create `terraform/modules/bootstrap/versions.tf`**

```hcl
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}
```

- [ ] **Step 2: Create `terraform/modules/bootstrap/providers.tf`**

```hcl
provider "google" {
  project = var.project_id
  region  = var.region
}
```

- [ ] **Step 3: Create `terraform/modules/bootstrap/variables.tf`**

```hcl
variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "teamster-332318"
}

variable "region" {
  description = "GCP region for the state bucket"
  type        = string
  default     = "us-central1"
}
```

- [ ] **Step 4: Create `terraform/modules/bootstrap/main.tf`**

```hcl
resource "google_storage_bucket" "terraform_state" {
  name     = "teamster-terraform-state"
  location = var.region
  project  = var.project_id

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle {
    prevent_destroy = true
  }
}
```

- [ ] **Step 5: Create `terraform/modules/bootstrap/outputs.tf`**

```hcl
output "bucket_name" {
  description = "Name of the Terraform state bucket"
  value       = google_storage_bucket.terraform_state.name
}
```

- [ ] **Step 6: Commit**

```bash
git add terraform/modules/bootstrap/
git commit -m "feat(terraform): add bootstrap module for state bucket"
```

---

## Task 3: GKE module

**Files:**

- Create: `terraform/modules/gke/main.tf`
- Create: `terraform/modules/gke/variables.tf`
- Create: `terraform/modules/gke/outputs.tf`

- [ ] **Step 1: Create `terraform/modules/gke/variables.tf`**

```hcl
variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for the cluster"
  type        = string
}

variable "cluster_name" {
  description = "GKE cluster name"
  type        = string
}
```

- [ ] **Step 2: Create `terraform/modules/gke/main.tf`**

```hcl
resource "google_container_cluster" "autopilot" {
  name     = var.cluster_name
  location = var.region
  project  = var.project_id

  enable_autopilot = true

  # Autopilot clusters manage node pools automatically.
  # Additional settings (release channel, networking, etc.) will be
  # reconciled after import — run `terraform plan` and adjust to match.
}
```

Note: GKE Autopilot clusters have many computed attributes. After importing, run
`terraform plan` and add any attributes that show drift until the plan is clean.
This is expected and may require several iterations. Consult the
[google_container_cluster docs](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/container_cluster)
for attribute reference.

- [ ] **Step 3: Create `terraform/modules/gke/outputs.tf`**

```hcl
output "cluster_endpoint" {
  description = "GKE cluster endpoint"
  value       = google_container_cluster.autopilot.endpoint
}

output "cluster_ca_certificate" {
  description = "Base64-encoded CA certificate for the cluster"
  value       = google_container_cluster.autopilot.master_auth[0].cluster_ca_certificate
  sensitive   = true
}

output "cluster_name" {
  description = "GKE cluster name"
  value       = google_container_cluster.autopilot.name
}
```

- [ ] **Step 4: Commit**

```bash
git add terraform/modules/gke/
git commit -m "feat(terraform): add GKE Autopilot module"
```

---

## Task 4: GCS module

**Files:**

- Create: `terraform/modules/gcs/main.tf`
- Create: `terraform/modules/gcs/variables.tf`
- Create: `terraform/modules/gcs/outputs.tf`

- [ ] **Step 1: Create `terraform/modules/gcs/variables.tf`**

```hcl
variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for the buckets"
  type        = string
}

variable "code_locations" {
  description = "List of code location names (creates teamster-<name> buckets)"
  type        = list(string)
}
```

- [ ] **Step 2: Create `terraform/modules/gcs/main.tf`**

```hcl
locals {
  # Production buckets: one per code location + test bucket
  buckets = merge(
    { for loc in var.code_locations : loc => "teamster-${loc}" },
    { "test" = "teamster-test" }
  )
}

resource "google_storage_bucket" "dagster" {
  for_each = local.buckets

  name     = each.value
  location = var.region
  project  = var.project_id

  uniform_bucket_level_access = true
}
```

- [ ] **Step 3: Create `terraform/modules/gcs/outputs.tf`**

```hcl
output "bucket_names" {
  description = "Map of code location key to bucket name"
  value       = { for k, b in google_storage_bucket.dagster : k => b.name }
}

output "bucket_urls" {
  description = "Map of code location key to gs:// URL"
  value       = { for k, b in google_storage_bucket.dagster : k => b.url }
}
```

- [ ] **Step 4: Commit**

```bash
git add terraform/modules/gcs/
git commit -m "feat(terraform): add GCS buckets module"
```

---

## Task 5: BigQuery module

**Files:**

- Create: `terraform/modules/bigquery/main.tf`
- Create: `terraform/modules/bigquery/variables.tf`
- Create: `terraform/modules/bigquery/outputs.tf`

- [ ] **Step 1: Create `terraform/modules/bigquery/variables.tf`**

```hcl
variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "location" {
  description = "BigQuery dataset location"
  type        = string
}

variable "production_datasets" {
  description = "Map of dataset_id to description for production datasets"
  type        = map(string)
}
```

- [ ] **Step 2: Create `terraform/modules/bigquery/main.tf`**

The production datasets are organized by code location. Personal dev datasets
(`dbt_cgibson_*`, `dbt_cbini_*`, `zz_*`, `z_dev_*`), dbt Cloud PR datasets
(`dbt_cloud_pr_*`), and archived datasets (`z_archive_*`) are NOT managed by
Terraform — they are ephemeral or user-owned.

```hcl
resource "google_bigquery_dataset" "production" {
  for_each = var.production_datasets

  dataset_id = each.key
  project    = var.project_id
  location   = var.location

  # Labels and descriptions will be reconciled after import.
}

resource "google_bigquery_connection" "biglake_gcs" {
  connection_id = "biglake-teamster-gcs"
  project       = var.project_id
  location      = var.location
  friendly_name = "BigLake - Teamster GCS"

  cloud_resource {}
}
```

- [ ] **Step 3: Create `terraform/modules/bigquery/outputs.tf`**

```hcl
output "dataset_ids" {
  description = "List of managed BigQuery dataset IDs"
  value       = [for d in google_bigquery_dataset.production : d.dataset_id]
}

output "biglake_connection_name" {
  description = "Fully-qualified BigLake connection name"
  value       = google_bigquery_connection.biglake_gcs.name
}
```

- [ ] **Step 4: Commit**

```bash
git add terraform/modules/bigquery/
git commit -m "feat(terraform): add BigQuery datasets and BigLake connection module"
```

---

## Task 6: Artifact Registry module

**Files:**

- Create: `terraform/modules/artifact_registry/main.tf`
- Create: `terraform/modules/artifact_registry/variables.tf`
- Create: `terraform/modules/artifact_registry/outputs.tf`

- [ ] **Step 1: Create `terraform/modules/artifact_registry/variables.tf`**

```hcl
variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for the registry"
  type        = string
}
```

- [ ] **Step 2: Create `terraform/modules/artifact_registry/main.tf`**

```hcl
resource "google_artifact_registry_repository" "teamster" {
  repository_id = "teamster"
  project       = var.project_id
  location      = var.region
  format        = "DOCKER"
  description   = "Container images for Dagster code locations"
}
```

- [ ] **Step 3: Create `terraform/modules/artifact_registry/outputs.tf`**

```hcl
output "repository_id" {
  description = "Artifact Registry repository ID"
  value       = google_artifact_registry_repository.teamster.repository_id
}

output "repository_url" {
  description = "Full Docker registry URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.teamster.repository_id}"
}
```

- [ ] **Step 4: Commit**

```bash
git add terraform/modules/artifact_registry/
git commit -m "feat(terraform): add Artifact Registry module"
```

---

## Task 7: IAM module

**Files:**

- Create: `terraform/modules/iam/main.tf`
- Create: `terraform/modules/iam/variables.tf`
- Create: `terraform/modules/iam/outputs.tf`

- [ ] **Step 1: Create `terraform/modules/iam/variables.tf`**

```hcl
variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "project_number" {
  description = "GCP project number"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "github_org" {
  description = "GitHub organization name"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
}

variable "artifact_registry_repository_id" {
  description = "Artifact Registry repository ID for CI/CD IAM binding"
  type        = string
}
```

- [ ] **Step 2: Create `terraform/modules/iam/main.tf`**

```hcl
# ---------------------------------------------------------------------------
# Dagster Cloud Agent service account (GKE Workload Identity)
# ---------------------------------------------------------------------------

resource "google_service_account" "dagster_agent" {
  account_id   = "user-cloud-dagster-cloud-agent"
  display_name = "Dagster Cloud Agent"
  project      = var.project_id
}

resource "google_project_iam_member" "dagster_agent_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.dagster_agent.email}"
}

resource "google_service_account_iam_member" "dagster_agent_workload_identity" {
  service_account_id = google_service_account.dagster_agent.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[dagster-cloud/${google_service_account.dagster_agent.account_id}]"
}

# ---------------------------------------------------------------------------
# GitHub Actions Workload Identity Federation
# ---------------------------------------------------------------------------

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  project                   = var.project_id
  display_name              = "GitHub Actions Pool"
}

resource "google_iam_workload_identity_pool_provider" "teamster" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "teamster"
  project                            = var.project_id
  display_name                       = "TEAMster Provider"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.actor"            = "assertion.actor"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
  }

  attribute_condition = "assertion.repository_owner == '${var.github_org}'"
}

resource "google_artifact_registry_repository_iam_member" "github_actions_push" {
  repository = var.artifact_registry_repository_id
  project    = var.project_id
  location   = var.region
  role       = "roles/artifactregistry.repoAdmin"
  member     = "principalSet://iam.googleapis.com/projects/${var.project_number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github.workload_identity_pool_id}/attribute.repository/${var.github_org}/${var.github_repo}"
}

# ---------------------------------------------------------------------------
# Domain-wide delegation documentation
# ---------------------------------------------------------------------------
#
# The Google Admin service account used for Workspace API calls (Directory,
# Sheets, Forms, Drive) requires domain-wide delegation configured in the
# Google Workspace admin console. This cannot be automated via Terraform.
#
# After applying, complete these manual steps:
#
# 1. Get the client ID:
#      terraform output workspace_delegation_client_id
#
# 2. Navigate to: admin.google.com > Security > Access and data control >
#    API controls > Domain-wide delegation > Add new
#
# 3. Enter the client ID and authorize these OAuth scopes:
#    - https://www.googleapis.com/auth/admin.directory.user
#    - https://www.googleapis.com/auth/admin.directory.user.readonly
#    - https://www.googleapis.com/auth/admin.directory.group
#    - https://www.googleapis.com/auth/admin.directory.group.readonly
#    - https://www.googleapis.com/auth/admin.directory.group.member
#    - https://www.googleapis.com/auth/spreadsheets
#    - https://www.googleapis.com/auth/forms.responses.readonly
#    - https://www.googleapis.com/auth/drive
#
# These scopes correspond to the Google Workspace APIs used by the Dagster
# code locations. The actual service account key is managed in 1Password
# (item: "Google Admin Service Account") and injected via the 1Password
# Operator on GKE.
```

- [ ] **Step 3: Create `terraform/modules/iam/outputs.tf`**

```hcl
output "dagster_agent_email" {
  description = "Dagster Cloud agent service account email"
  value       = google_service_account.dagster_agent.email
}

output "dagster_agent_account_id" {
  description = "Dagster Cloud agent service account ID (for k8s annotation)"
  value       = google_service_account.dagster_agent.account_id
}

output "workload_identity_pool_name" {
  description = "Fully-qualified Workload Identity Pool name"
  value       = google_iam_workload_identity_pool.github.name
}

output "workload_identity_provider_name" {
  description = "Fully-qualified Workload Identity Provider name"
  value       = google_iam_workload_identity_pool_provider.teamster.name
}

output "workspace_delegation_client_id" {
  description = "Client ID for Google Workspace domain-wide delegation (paste into admin console)"
  value       = google_service_account.dagster_agent.unique_id
}
```

- [ ] **Step 4: Commit**

```bash
git add terraform/modules/iam/
git commit -m "feat(terraform): add IAM module with Workload Identity and delegation docs"
```

---

## Task 8: Kubernetes module

**Files:**

- Create: `terraform/modules/k8s/main.tf`
- Create: `terraform/modules/k8s/variables.tf`
- Create: `terraform/modules/k8s/outputs.tf`
- Create: `terraform/modules/k8s/onepassword_items.tf`
- Create: `terraform/modules/k8s/helm_dagster.tf`
- Create: `terraform/modules/k8s/helm_onepassword.tf`

- [ ] **Step 1: Create `terraform/modules/k8s/variables.tf`**

```hcl
variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "dagster_agent_email" {
  description = "Dagster Cloud agent service account email (for GKE Workload Identity annotation)"
  type        = string
}

variable "dagster_agent_account_id" {
  description = "Dagster Cloud agent service account ID (for k8s SA name)"
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace for Dagster Cloud"
  type        = string
  default     = "dagster-cloud"
}
```

- [ ] **Step 2: Create `terraform/modules/k8s/main.tf`**

```hcl
resource "kubernetes_namespace" "dagster_cloud" {
  metadata {
    name = var.namespace
  }
}

resource "kubernetes_service_account" "dagster_agent" {
  metadata {
    name      = var.dagster_agent_account_id
    namespace = kubernetes_namespace.dagster_cloud.metadata[0].name

    annotations = {
      "iam.gke.io/gcp-service-account" = var.dagster_agent_email
    }
  }
}
```

- [ ] **Step 3: Create `terraform/modules/k8s/helm_dagster.tf`**

```hcl
resource "helm_release" "dagster_cloud_agent" {
  name       = "user-cloud"
  repository = "https://dagster-io.github.io/helm-user-cloud"
  chart      = "dagster-cloud-agent"
  namespace  = kubernetes_namespace.dagster_cloud.metadata[0].name

  # Pin chart version after import — run `helm list -n dagster-cloud` to get
  # the current version, then set it here.
  # version = "X.Y.Z"

  values = [
    file("${path.module}/values/dagster-agent.yaml")
  ]
}
```

- [ ] **Step 4: Create `terraform/modules/k8s/values/dagster-agent.yaml`**

This is the existing `.k8s/dagster/values-override.yaml` content, moved into the
module:

```yaml
dagsterCloud:
  deployments:
    - prod
  branchDeployments: true

dagsterCloudAgent:
  resources:
    requests:
      cpu: 500m
      memory: 0.5Gi
    limits:
      cpu: 750m
      memory: 1.0Gi
  podSecurityContext:
    runAsUser: 1001
  nodeSelector:
    cloud.google.com/gke-spot: "true"
  terminationGracePeriodSeconds: 15
  replicas: 2
  affinity:
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        - labelSelector:
            matchExpressions:
              - key: app.kubernetes.io/name
                operator: In
                values:
                  - dagster-cloud-agent
          topologyKey: kubernetes.io/hostname

workspace:
  serverK8sConfig:
    containerConfig:
      resources:
        requests:
          cpu: 500m
          memory: 2.0Gi
        limits:
          cpu: 750m
          memory: 2.5Gi
    podTemplateSpecMetadata:
      annotations:
        operator.1password.io/auto-restart: "true"
    podSpecConfig:
      nodeSelector:
        cloud.google.com/compute-class: Scale-Out
        cloud.google.com/gke-spot: "true"
        kubernetes.io/arch: arm64
      terminationGracePeriodSeconds: 15
  runK8sConfig:
    containerConfig:
      resources:
        requests:
          cpu: 500m
          memory: 2.0Gi
        limits:
          cpu: 750m
          memory: 2.5Gi
    podTemplateSpecMetadata:
      annotations:
        cluster-autoscaler.kubernetes.io/safe-to-evict: "false"
    podSpecConfig:
      nodeSelector:
        cloud.google.com/compute-class: Scale-Out
        kubernetes.io/arch: arm64
  serverTTL:
    branchDeployments:
      ttlSeconds: 900

extraManifests:
  - apiVersion: policy/v1
    kind: PodDisruptionBudget
    metadata:
      name: dca-pdb
    spec:
      maxUnavailable: 1
      selector:
        matchLabels:
          app.kubernetes.io/instance: user-cloud
          app.kubernetes.io/name: dagster-cloud-agent
          component: agent
          deployment: agent
  - apiVersion: policy/v1
    kind: PodDisruptionBudget
    metadata:
      name: kippcamden-pdb
    spec:
      maxUnavailable: 1
      selector:
        matchLabels:
          deployment_name: prod
          managed_by: K8sUserCodeLauncher
          location_name: kippcamden
  - apiVersion: policy/v1
    kind: PodDisruptionBudget
    metadata:
      name: kippmiami-pdb
    spec:
      maxUnavailable: 1
      selector:
        matchLabels:
          deployment_name: prod
          managed_by: K8sUserCodeLauncher
          location_name: kippmiami
  - apiVersion: policy/v1
    kind: PodDisruptionBudget
    metadata:
      name: kippnewark-pdb
    spec:
      maxUnavailable: 1
      selector:
        matchLabels:
          deployment_name: prod
          managed_by: K8sUserCodeLauncher
          location_name: kippnewark
  - apiVersion: policy/v1
    kind: PodDisruptionBudget
    metadata:
      name: kipppaterson-pdb
    spec:
      maxUnavailable: 1
      selector:
        matchLabels:
          deployment_name: prod
          managed_by: K8sUserCodeLauncher
          location_name: kipppaterson
  - apiVersion: policy/v1
    kind: PodDisruptionBudget
    metadata:
      name: kipptaf-pdb
    spec:
      maxUnavailable: 1
      selector:
        matchLabels:
          deployment_name: prod
          managed_by: K8sUserCodeLauncher
          location_name: kipptaf
```

- [ ] **Step 5: Create `terraform/modules/k8s/helm_onepassword.tf`**

```hcl
resource "helm_release" "onepassword_connect" {
  name       = "connect"
  repository = "https://1password.github.io/connect-helm-charts/"
  chart      = "connect"
  namespace  = kubernetes_namespace.dagster_cloud.metadata[0].name

  # Pin chart version after import — run `helm list -n dagster-cloud` to get
  # the current version, then set it here.
  # version = "X.Y.Z"

  # The 1Password credentials file and connect token are injected at install
  # time via set/set-file flags. Terraform manages the Helm release config
  # but these sensitive values must be provided at apply time.
  #
  # To set them, use:
  #   terraform apply \
  #     -var="onepassword_credentials_file=/etc/secret-volume/1password-credentials.json" \
  #     -var="onepassword_connect_token=<token>"
  #
  # Or configure them in terraform.tfvars (not committed).

  values = [
    file("${path.module}/values/onepassword-connect.yaml")
  ]
}
```

- [ ] **Step 6: Create `terraform/modules/k8s/values/onepassword-connect.yaml`**

```yaml
connect:
  api:
    resources:
      requests:
        cpu: 250m
        memory: 0.5Gi
      limits:
        cpu: 500m
        memory: 1.0Gi
  sync:
    resources:
      requests:
        cpu: 250m
        memory: 0.5Gi
      limits:
        cpu: 500m
        memory: 1.0Gi
  nodeSelector:
    cloud.google.com/gke-spot: "true"

operator:
  create: true
  autoRestart: true
  resources:
    requests:
      cpu: 250m
      memory: 0.5Gi
    limits:
      cpu: 500m
      memory: 1.0Gi
  nodeSelector:
    cloud.google.com/gke-spot: "true"
```

- [ ] **Step 7: Create `terraform/modules/k8s/onepassword_items.tf`**

```hcl
locals {
  onepassword_items = {
    "op-adp-wfn-sftp"               = "vaults/Data Team/items/ADP Workforce Now SFTP"
    "op-adp-wfm-api"                = "vaults/Data Team/items/ADP Workforce Manager API"
    "op-adp-wfn-api"                = "vaults/Data Team/items/ADP Workforce Now API"
    "op-airbyte-api"                = "vaults/Data Team/items/Airbyte API"
    "op-amplify-service-account"    = "vaults/Data Team/items/Amplify Service Account"
    "op-amplify-dds-service-account" = "vaults/Data Team/items/DIBELS Data System"
    "op-clever-sftp"                = "vaults/Data Team/items/Clever SFTP - Uploads"
    "op-couchdrop-sftp"             = "vaults/Data Team/items/Couchdrop SFTP - Data Robot"
    "op-coupa-sftp"                 = "vaults/Data Team/items/Coupa SFTP"
    "op-coupa-api"                  = "vaults/Data Team/items/Coupa API"
    "op-deanslist-sftp"             = "vaults/Data Team/items/DeansList SFTP"
    "op-egencia-sftp"               = "vaults/Data Team/items/Egencia SFTP"
    "op-illuminate-sftp"            = "vaults/Data Team/items/Illuminate SFTP"
    "op-iready-sftp"                = "vaults/Data Team/items/iReady SFTP"
    "op-edplan-sftp-kippcamden"     = "vaults/Data Team/items/edplan SFTP - Camden"
    "op-ps-db-kippcamden"           = "vaults/Data Team/items/PowerSchool DB - Camden"
    "op-ps-ssh-kippcamden"          = "vaults/Data Team/items/PowerSchool SSH - Camden"
    "op-titan-sftp-kippcamden"      = "vaults/Data Team/items/Titan SFTP - Camden"
    "op-ps-db-kippmiami"            = "vaults/Data Team/items/PowerSchool DB - Miami"
    "op-ps-ssh-kippmiami"           = "vaults/Data Team/items/PowerSchool SSH - Miami"
    "op-renlearn-sftp-kippmiami"    = "vaults/Data Team/items/RenLearning SFTP Exports - Miami"
    "op-edplan-sftp-kippnewark"     = "vaults/Data Team/items/edplan SFTP - Newark"
    "op-ps-db-kippnewark"           = "vaults/Data Team/items/PowerSchool DB - Newark"
    "op-ps-ssh-kippnewark"          = "vaults/Data Team/items/PowerSchool SSH - Newark"
    "op-titan-sftp-kippnewark"      = "vaults/Data Team/items/Titan SFTP - Newark"
    "op-renlearn-sftp-kippnj"       = "vaults/Data Team/items/RenLearning SFTP Exports - NJ"
    "op-idauto-sftp"                = "vaults/Data Team/items/ID Auto SFTP"
    "op-ldap-service-account"       = "vaults/Data Team/items/Active Directory Service Account"
    "op-littlesis-sftp"             = "vaults/Data Team/items/Little SIS SFTP"
    "op-schoolmint-grow-api"        = "vaults/Data Team/items/SchooMint Grow API"
    "op-smartrecruiters-api"        = "vaults/Data Team/items/SmartRecruiters API"
    "op-ps-db-staging"              = "vaults/Data Team/items/PowerSchool DB - Test"
    "op-ps-ssh-staging"             = "vaults/Data Team/items/PowerSchool SSH - Test"
    "op-zendesk-api"                = "vaults/Data Team/items/Zendesk API"
    "op-deanslist-api"              = "vaults/Data Team/items/DeansList API"
    "op-tableau-server-api"         = "vaults/Data Team/items/Tableau Server PAT - Dagster"
    "op-illuminate-odbc"            = "vaults/Data Team/items/Illuminate ODBC"
    "op-google-admin-service-account" = "vaults/Data Team/items/Google Admin Service Account"
    "op-powerschool-enrollment-api" = "vaults/Data Team/items/PowerSchool Enrollment"
    "op-overgrad-api-kippnewark"    = "vaults/Data Team/items/Overgrad API - Newark"
    "op-overgrad-api-kippcamden"    = "vaults/Data Team/items/Overgrad API - Camden"
    "op-outlook-pm"                 = "vaults/Data Team/items/Outlook - Performance Management"
    "op-knowbe4"                    = "vaults/Data Team/items/KnowBe4 Reporting REST API"
    "op-amplify-sftp-kipptaf"       = "vaults/Data Team/items/Amplify SFTP"
    "op-amplify-sftp-kipppaterson"  = "vaults/Data Team/items/Amplify SFTP - Paterson"
  }
}

resource "kubernetes_manifest" "onepassword_items" {
  for_each = local.onepassword_items

  manifest = {
    apiVersion = "onepassword.com/v1"
    kind       = "OnePasswordItem"
    metadata = {
      name      = each.key
      namespace = kubernetes_namespace.dagster_cloud.metadata[0].name
    }
    spec = {
      itemPath = each.value
    }
  }
}
```

- [ ] **Step 8: Create `terraform/modules/k8s/outputs.tf`**

```hcl
output "namespace" {
  description = "Kubernetes namespace name"
  value       = kubernetes_namespace.dagster_cloud.metadata[0].name
}

output "dagster_agent_release_name" {
  description = "Dagster Cloud agent Helm release name"
  value       = helm_release.dagster_cloud_agent.name
}

output "onepassword_release_name" {
  description = "1Password Connect Helm release name"
  value       = helm_release.onepassword_connect.name
}
```

- [ ] **Step 9: Commit**

```bash
git add terraform/modules/k8s/
git commit -m "feat(terraform): add k8s module with Dagster, 1Password Helm, and secret items"
```

---

## Task 9: GitHub module

**Files:**

- Create: `terraform/modules/github/main.tf`
- Create: `terraform/modules/github/variables.tf`
- Create: `terraform/modules/github/outputs.tf`

- [ ] **Step 1: Create `terraform/modules/github/variables.tf`**

```hcl
variable "github_org" {
  description = "GitHub organization name"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
}

variable "gcp_project_id" {
  description = "GCP project ID (stored as Actions variable)"
  type        = string
}

variable "gcp_project_number" {
  description = "GCP project number (stored as Actions variable)"
  type        = string
}

variable "gcp_region" {
  description = "GCP region (stored as Actions variable)"
  type        = string
}

variable "dagster_organization_id" {
  description = "Dagster Cloud organization ID (stored as Actions variable)"
  type        = string
  default     = "kipptaf"
}
```

- [ ] **Step 2: Create `terraform/modules/github/main.tf`**

```hcl
data "github_repository" "teamster" {
  full_name = "${var.github_org}/${var.github_repo}"
}

resource "github_branch_protection" "main" {
  repository_id = data.github_repository.teamster.node_id
  pattern       = "main"

  # Branch protection settings will be reconciled after import.
  # Run `terraform plan` and adjust to match current settings.
}

# ---------------------------------------------------------------------------
# GitHub Actions variables (non-sensitive)
# ---------------------------------------------------------------------------

resource "github_actions_variable" "gcp_project_id" {
  repository    = var.github_repo
  variable_name = "GCP_PROJECT_ID"
  value         = var.gcp_project_id
}

resource "github_actions_variable" "gcp_project_number" {
  repository    = var.github_repo
  variable_name = "GCP_PROJECT_NUMBER"
  value         = var.gcp_project_number
}

resource "github_actions_variable" "gcp_region" {
  repository    = var.github_repo
  variable_name = "GCP_REGION"
  value         = var.gcp_region
}

resource "github_actions_variable" "dagster_organization_id" {
  repository    = var.github_repo
  variable_name = "DAGSTER_ORGANIZATION_ID"
  value         = var.dagster_organization_id
}

# ---------------------------------------------------------------------------
# GitHub Actions secrets (sensitive — values provided at apply time)
# ---------------------------------------------------------------------------
# Secrets cannot be read back from GitHub — Terraform can only create/update
# them. After import, these will always show as "changed" on first plan.
# That is expected behavior.
#
# The DAGSTER_CLOUD_AGENT_TOKEN value must be provided via:
#   terraform apply -var="dagster_cloud_agent_token=<token>"
# ---------------------------------------------------------------------------
```

- [ ] **Step 3: Create `terraform/modules/github/outputs.tf`**

```hcl
output "repository_full_name" {
  description = "Full repository name (org/repo)"
  value       = data.github_repository.teamster.full_name
}
```

- [ ] **Step 4: Commit**

```bash
git add terraform/modules/github/
git commit -m "feat(terraform): add GitHub module with branch protection and Actions config"
```

---

## Task 10: Root module composition (main.tf, outputs.tf, imports.tf)

**Files:**

- Create: `terraform/main.tf`
- Create: `terraform/outputs.tf`
- Create: `terraform/imports.tf`

- [ ] **Step 1: Create `terraform/main.tf`**

```hcl
module "gke" {
  source = "./modules/gke"

  project_id   = var.project_id
  region       = var.region
  cluster_name = var.gke_cluster_name
}

module "gcs" {
  source = "./modules/gcs"

  project_id     = var.project_id
  region         = var.region
  code_locations = var.code_locations
}

module "bigquery" {
  source = "./modules/bigquery"

  project_id          = var.project_id
  location            = var.bigquery_location
  production_datasets = local.production_datasets
}

module "artifact_registry" {
  source = "./modules/artifact_registry"

  project_id = var.project_id
  region     = var.region
}

module "iam" {
  source = "./modules/iam"

  project_id                      = var.project_id
  project_number                  = var.project_number
  region                          = var.region
  github_org                      = var.github_org
  github_repo                     = var.github_repo
  artifact_registry_repository_id = module.artifact_registry.repository_id
}

module "k8s" {
  source = "./modules/k8s"

  project_id               = var.project_id
  dagster_agent_email      = module.iam.dagster_agent_email
  dagster_agent_account_id = module.iam.dagster_agent_account_id

  depends_on = [module.gke]
}

module "github" {
  source = "./modules/github"

  github_org         = var.github_org
  github_repo        = var.github_repo
  gcp_project_id     = var.project_id
  gcp_project_number = var.project_number
  gcp_region         = var.region
}

# ---------------------------------------------------------------------------
# Production BigQuery datasets
# ---------------------------------------------------------------------------
# Only production datasets are managed. Personal dev (dbt_cgibson_*, zz_*),
# dbt Cloud PR (dbt_cloud_pr_*), archived (z_archive_*), and dev (z_dev_*)
# datasets are NOT managed — they are ephemeral or user-owned.
# ---------------------------------------------------------------------------

locals {
  production_datasets = {
    # Infrastructure
    "airbyte_internal" = "Airbyte internal metadata"
    "functions"        = "Cloud Functions"
    "rostering"        = "Rostering"

    # DLT pipelines
    "dagster_kipptaf_dlt_illuminate_codes"                = "DLT: Illuminate codes"
    "dagster_kipptaf_dlt_illuminate_dna_assessments"      = "DLT: Illuminate DNA assessments"
    "dagster_kipptaf_dlt_illuminate_dna_repositories"     = "DLT: Illuminate DNA repositories"
    "dagster_kipptaf_dlt_illuminate_national_assessments" = "DLT: Illuminate national assessments"
    "dagster_kipptaf_dlt_illuminate_public"               = "DLT: Illuminate public"
    "dagster_kipptaf_dlt_illuminate_standards"            = "DLT: Illuminate standards"
    "dagster_kipptaf_dlt_zendesk_support"                 = "DLT: Zendesk support"
    "dagster_kipptaf_dlt_zendesk_support_staging"         = "DLT: Zendesk support staging"

    # KIPP Camden
    "kippcamden_dbt_test__audit" = "KIPP Camden: dbt test audit"
    "kippcamden_deanslist"       = "KIPP Camden: DeansList"
    "kippcamden_edplan"          = "KIPP Camden: edplan"
    "kippcamden_extracts"        = "KIPP Camden: extracts"
    "kippcamden_finalsite"       = "KIPP Camden: Finalsite"
    "kippcamden_overgrad"        = "KIPP Camden: Overgrad"
    "kippcamden_pearson"         = "KIPP Camden: Pearson"
    "kippcamden_powerschool"     = "KIPP Camden: PowerSchool"
    "kippcamden_titan"           = "KIPP Camden: Titan"

    # KIPP Miami
    "kippmiami_dbt_test__audit" = "KIPP Miami: dbt test audit"
    "kippmiami_deanslist"       = "KIPP Miami: DeansList"
    "kippmiami_extracts"        = "KIPP Miami: extracts"
    "kippmiami_finalsite"       = "KIPP Miami: Finalsite"
    "kippmiami_fldoe"           = "KIPP Miami: FLDOE"
    "kippmiami_iready"          = "KIPP Miami: iReady"
    "kippmiami_powerschool"     = "KIPP Miami: PowerSchool"
    "kippmiami_renlearn"        = "KIPP Miami: Renaissance Learning"

    # KIPP Newark
    "kippnewark_amplify"         = "KIPP Newark: Amplify"
    "kippnewark_dbt_test__audit" = "KIPP Newark: dbt test audit"
    "kippnewark_deanslist"       = "KIPP Newark: DeansList"
    "kippnewark_edplan"          = "KIPP Newark: edplan"
    "kippnewark_extracts"        = "KIPP Newark: extracts"
    "kippnewark_finalsite"       = "KIPP Newark: Finalsite"
    "kippnewark_iready"          = "KIPP Newark: iReady"
    "kippnewark_overgrad"        = "KIPP Newark: Overgrad"
    "kippnewark_pearson"         = "KIPP Newark: Pearson"
    "kippnewark_powerschool"     = "KIPP Newark: PowerSchool"
    "kippnewark_renlearn"        = "KIPP Newark: Renaissance Learning"
    "kippnewark_titan"           = "KIPP Newark: Titan"

    # KIPP NJ (shared)
    "kippnj_iready"   = "KIPP NJ: iReady (shared)"
    "kippnj_renlearn"  = "KIPP NJ: Renaissance Learning (shared)"

    # KIPP Paterson
    "kipppaterson_amplify"         = "KIPP Paterson: Amplify"
    "kipppaterson_dbt_test__audit" = "KIPP Paterson: dbt test audit"
    "kipppaterson_finalsite"       = "KIPP Paterson: Finalsite"
    "kipppaterson_pearson"         = "KIPP Paterson: Pearson"
    "kipppaterson_powerschool"     = "KIPP Paterson: PowerSchool"

    # KIPP TAF (org-wide)
    "kipptaf"                          = "KIPP TAF: core"
    "kipptaf_accounting"               = "KIPP TAF: accounting"
    "kipptaf_act"                      = "KIPP TAF: ACT"
    "kipptaf_adp_payroll"              = "KIPP TAF: ADP payroll"
    "kipptaf_adp_workforce_manager"    = "KIPP TAF: ADP Workforce Manager"
    "kipptaf_adp_workforce_now"        = "KIPP TAF: ADP Workforce Now"
    "kipptaf_alchemer"                 = "KIPP TAF: Alchemer"
    "kipptaf_amplify"                  = "KIPP TAF: Amplify"
    "kipptaf_appsheet"                 = "KIPP TAF: AppSheet"
    "kipptaf_assessments"              = "KIPP TAF: assessments"
    "kipptaf_collegeboard"             = "KIPP TAF: College Board"
    "kipptaf_coupa"                    = "KIPP TAF: Coupa"
    "kipptaf_crdc"                     = "KIPP TAF: CRDC"
    "kipptaf_dayforce"                 = "KIPP TAF: Dayforce"
    "kipptaf_dbt_test__audit"          = "KIPP TAF: dbt test audit"
    "kipptaf_deanslist"                = "KIPP TAF: DeansList"
    "kipptaf_edplan"                   = "KIPP TAF: edplan"
    "kipptaf_egencia"                  = "KIPP TAF: Egencia"
    "kipptaf_extracts"                 = "KIPP TAF: extracts"
    "kipptaf_finalsite"                = "KIPP TAF: Finalsite"
    "kipptaf_finance"                  = "KIPP TAF: finance"
    "kipptaf_fldoe"                    = "KIPP TAF: FLDOE"
    "kipptaf_google_appsheet"          = "KIPP TAF: Google AppSheet"
    "kipptaf_google_directory"         = "KIPP TAF: Google Directory"
    "kipptaf_google_forms"             = "KIPP TAF: Google Forms"
    "kipptaf_google_sheets"            = "KIPP TAF: Google Sheets"
    "kipptaf_hubspot"                  = "KIPP TAF: HubSpot"
    "kipptaf_illuminate"               = "KIPP TAF: Illuminate"
    "kipptaf_instagram_business"       = "KIPP TAF: Instagram Business"
    "kipptaf_iready"                   = "KIPP TAF: iReady"
    "kipptaf_kippadb"                  = "KIPP TAF: KIPP ADB"
    "kipptaf_knowbe4"                  = "KIPP TAF: KnowBe4"
    "kipptaf_ldap"                     = "KIPP TAF: LDAP"
    "kipptaf_marts"                    = "KIPP TAF: data marts"
    "kipptaf_metrics"                  = "KIPP TAF: metrics"
    "kipptaf_njdoe"                    = "KIPP TAF: NJDOE"
    "kipptaf_nsc"                      = "KIPP TAF: NSC"
    "kipptaf_overgrad"                 = "KIPP TAF: Overgrad"
    "kipptaf_pearson"                  = "KIPP TAF: Pearson"
    "kipptaf_people"                   = "KIPP TAF: people"
    "kipptaf_performance_management"   = "KIPP TAF: performance management"
    "kipptaf_powerschool"              = "KIPP TAF: PowerSchool"
    "kipptaf_powerschool_enrollment"   = "KIPP TAF: PowerSchool Enrollment"
    "kipptaf_qa"                       = "KIPP TAF: QA"
    "kipptaf_renlearn"                 = "KIPP TAF: Renaissance Learning"
    "kipptaf_reporting"                = "KIPP TAF: reporting"
    "kipptaf_schoolmint_grow"          = "KIPP TAF: SchoolMint Grow"
    "kipptaf_smartrecruiters"          = "KIPP TAF: SmartRecruiters"
    "kipptaf_students"                 = "KIPP TAF: students"
    "kipptaf_surveys"                  = "KIPP TAF: surveys"
    "kipptaf_tableau"                  = "KIPP TAF: Tableau"
    "kipptaf_titan"                    = "KIPP TAF: Titan"
    "kipptaf_topline"                  = "KIPP TAF: topline"
    "kipptaf_utils"                    = "KIPP TAF: utils"
    "kipptaf_zendesk"                  = "KIPP TAF: Zendesk"

    # Other
    "teamster_kipppaterson" = "KIPP Paterson: legacy"
    "topline_scratch"       = "Topline scratch"
  }
}
```

- [ ] **Step 2: Create `terraform/outputs.tf`**

```hcl
output "gke_cluster_endpoint" {
  description = "GKE cluster endpoint"
  value       = module.gke.cluster_endpoint
}

output "gcs_bucket_names" {
  description = "Map of code location to GCS bucket name"
  value       = module.gcs.bucket_names
}

output "bigquery_dataset_ids" {
  description = "List of managed BigQuery dataset IDs"
  value       = module.bigquery.dataset_ids
}

output "artifact_registry_url" {
  description = "Artifact Registry Docker URL"
  value       = module.artifact_registry.repository_url
}

output "dagster_agent_email" {
  description = "Dagster Cloud agent service account email"
  value       = module.iam.dagster_agent_email
}

output "workload_identity_provider" {
  description = "Workload Identity Provider name (for GitHub Actions)"
  value       = module.iam.workload_identity_provider_name
}

output "workspace_delegation_client_id" {
  description = "Client ID for Workspace domain-wide delegation (paste into admin console)"
  value       = module.iam.workspace_delegation_client_id
}

output "k8s_namespace" {
  description = "Kubernetes namespace"
  value       = module.k8s.namespace
}
```

- [ ] **Step 3: Create `terraform/imports.tf`**

This file contains all `import` blocks for existing resources. After the first
successful `terraform apply` (which performs the imports), these blocks can
remain in the code as documentation or be removed.

```hcl
# ---------------------------------------------------------------------------
# GKE
# ---------------------------------------------------------------------------

import {
  to = module.gke.google_container_cluster.autopilot
  id = "projects/teamster-332318/locations/us-central1/clusters/autopilot-cluster-dagster-hybrid-1"
}

# ---------------------------------------------------------------------------
# GCS buckets
# ---------------------------------------------------------------------------

import {
  to = module.gcs.google_storage_bucket.dagster["kipptaf"]
  id = "teamster-kipptaf"
}

import {
  to = module.gcs.google_storage_bucket.dagster["kippnewark"]
  id = "teamster-kippnewark"
}

import {
  to = module.gcs.google_storage_bucket.dagster["kippcamden"]
  id = "teamster-kippcamden"
}

import {
  to = module.gcs.google_storage_bucket.dagster["kippmiami"]
  id = "teamster-kippmiami"
}

import {
  to = module.gcs.google_storage_bucket.dagster["kipppaterson"]
  id = "teamster-kipppaterson"
}

import {
  to = module.gcs.google_storage_bucket.dagster["test"]
  id = "teamster-test"
}

# ---------------------------------------------------------------------------
# Artifact Registry
# ---------------------------------------------------------------------------

import {
  to = module.artifact_registry.google_artifact_registry_repository.teamster
  id = "projects/teamster-332318/locations/us-central1/repositories/teamster"
}

# ---------------------------------------------------------------------------
# IAM — service accounts
# ---------------------------------------------------------------------------

import {
  to = module.iam.google_service_account.dagster_agent
  id = "projects/teamster-332318/serviceAccounts/user-cloud-dagster-cloud-agent@teamster-332318.iam.gserviceaccount.com"
}

# ---------------------------------------------------------------------------
# IAM — Workload Identity Federation
# ---------------------------------------------------------------------------

import {
  to = module.iam.google_iam_workload_identity_pool.github
  id = "projects/teamster-332318/locations/global/workloadIdentityPools/github"
}

import {
  to = module.iam.google_iam_workload_identity_pool_provider.teamster
  id = "projects/teamster-332318/locations/global/workloadIdentityPools/github/providers/teamster"
}

# ---------------------------------------------------------------------------
# BigQuery — connection
# ---------------------------------------------------------------------------

import {
  to = module.bigquery.google_bigquery_connection.biglake_gcs
  id = "projects/teamster-332318/locations/us/connections/biglake-teamster-gcs"
}

# ---------------------------------------------------------------------------
# BigQuery — datasets (production only)
# ---------------------------------------------------------------------------
# Generated from the production dataset list. Each import block maps a
# dataset ID to the Terraform resource address.
#
# To regenerate this list if datasets change, query:
#   SELECT schema_name FROM INFORMATION_SCHEMA.SCHEMATA
#   WHERE schema_name NOT LIKE 'dbt_%' AND schema_name NOT LIKE 'z_%'
#     AND schema_name NOT LIKE 'zz_%' AND schema_name NOT LIKE 'dbt_cloud_pr_%'
# ---------------------------------------------------------------------------

import {
  to = module.bigquery.google_bigquery_dataset.production["airbyte_internal"]
  id = "projects/teamster-332318/datasets/airbyte_internal"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["functions"]
  id = "projects/teamster-332318/datasets/functions"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["rostering"]
  id = "projects/teamster-332318/datasets/rostering"
}

# DLT datasets
import {
  to = module.bigquery.google_bigquery_dataset.production["dagster_kipptaf_dlt_illuminate_codes"]
  id = "projects/teamster-332318/datasets/dagster_kipptaf_dlt_illuminate_codes"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["dagster_kipptaf_dlt_illuminate_dna_assessments"]
  id = "projects/teamster-332318/datasets/dagster_kipptaf_dlt_illuminate_dna_assessments"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["dagster_kipptaf_dlt_illuminate_dna_repositories"]
  id = "projects/teamster-332318/datasets/dagster_kipptaf_dlt_illuminate_dna_repositories"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["dagster_kipptaf_dlt_illuminate_national_assessments"]
  id = "projects/teamster-332318/datasets/dagster_kipptaf_dlt_illuminate_national_assessments"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["dagster_kipptaf_dlt_illuminate_public"]
  id = "projects/teamster-332318/datasets/dagster_kipptaf_dlt_illuminate_public"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["dagster_kipptaf_dlt_illuminate_standards"]
  id = "projects/teamster-332318/datasets/dagster_kipptaf_dlt_illuminate_standards"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["dagster_kipptaf_dlt_zendesk_support"]
  id = "projects/teamster-332318/datasets/dagster_kipptaf_dlt_zendesk_support"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["dagster_kipptaf_dlt_zendesk_support_staging"]
  id = "projects/teamster-332318/datasets/dagster_kipptaf_dlt_zendesk_support_staging"
}

# KIPP Camden datasets
import {
  to = module.bigquery.google_bigquery_dataset.production["kippcamden_dbt_test__audit"]
  id = "projects/teamster-332318/datasets/kippcamden_dbt_test__audit"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippcamden_deanslist"]
  id = "projects/teamster-332318/datasets/kippcamden_deanslist"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippcamden_edplan"]
  id = "projects/teamster-332318/datasets/kippcamden_edplan"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippcamden_extracts"]
  id = "projects/teamster-332318/datasets/kippcamden_extracts"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippcamden_finalsite"]
  id = "projects/teamster-332318/datasets/kippcamden_finalsite"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippcamden_overgrad"]
  id = "projects/teamster-332318/datasets/kippcamden_overgrad"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippcamden_pearson"]
  id = "projects/teamster-332318/datasets/kippcamden_pearson"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippcamden_powerschool"]
  id = "projects/teamster-332318/datasets/kippcamden_powerschool"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippcamden_titan"]
  id = "projects/teamster-332318/datasets/kippcamden_titan"
}

# KIPP Miami datasets
import {
  to = module.bigquery.google_bigquery_dataset.production["kippmiami_dbt_test__audit"]
  id = "projects/teamster-332318/datasets/kippmiami_dbt_test__audit"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippmiami_deanslist"]
  id = "projects/teamster-332318/datasets/kippmiami_deanslist"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippmiami_extracts"]
  id = "projects/teamster-332318/datasets/kippmiami_extracts"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippmiami_finalsite"]
  id = "projects/teamster-332318/datasets/kippmiami_finalsite"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippmiami_fldoe"]
  id = "projects/teamster-332318/datasets/kippmiami_fldoe"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippmiami_iready"]
  id = "projects/teamster-332318/datasets/kippmiami_iready"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippmiami_powerschool"]
  id = "projects/teamster-332318/datasets/kippmiami_powerschool"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippmiami_renlearn"]
  id = "projects/teamster-332318/datasets/kippmiami_renlearn"
}

# KIPP Newark datasets
import {
  to = module.bigquery.google_bigquery_dataset.production["kippnewark_amplify"]
  id = "projects/teamster-332318/datasets/kippnewark_amplify"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippnewark_dbt_test__audit"]
  id = "projects/teamster-332318/datasets/kippnewark_dbt_test__audit"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippnewark_deanslist"]
  id = "projects/teamster-332318/datasets/kippnewark_deanslist"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippnewark_edplan"]
  id = "projects/teamster-332318/datasets/kippnewark_edplan"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippnewark_extracts"]
  id = "projects/teamster-332318/datasets/kippnewark_extracts"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippnewark_finalsite"]
  id = "projects/teamster-332318/datasets/kippnewark_finalsite"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippnewark_iready"]
  id = "projects/teamster-332318/datasets/kippnewark_iready"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippnewark_overgrad"]
  id = "projects/teamster-332318/datasets/kippnewark_overgrad"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippnewark_pearson"]
  id = "projects/teamster-332318/datasets/kippnewark_pearson"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippnewark_powerschool"]
  id = "projects/teamster-332318/datasets/kippnewark_powerschool"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippnewark_renlearn"]
  id = "projects/teamster-332318/datasets/kippnewark_renlearn"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippnewark_titan"]
  id = "projects/teamster-332318/datasets/kippnewark_titan"
}

# KIPP NJ datasets
import {
  to = module.bigquery.google_bigquery_dataset.production["kippnj_iready"]
  id = "projects/teamster-332318/datasets/kippnj_iready"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kippnj_renlearn"]
  id = "projects/teamster-332318/datasets/kippnj_renlearn"
}

# KIPP Paterson datasets
import {
  to = module.bigquery.google_bigquery_dataset.production["kipppaterson_amplify"]
  id = "projects/teamster-332318/datasets/kipppaterson_amplify"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipppaterson_dbt_test__audit"]
  id = "projects/teamster-332318/datasets/kipppaterson_dbt_test__audit"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipppaterson_finalsite"]
  id = "projects/teamster-332318/datasets/kipppaterson_finalsite"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipppaterson_pearson"]
  id = "projects/teamster-332318/datasets/kipppaterson_pearson"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipppaterson_powerschool"]
  id = "projects/teamster-332318/datasets/kipppaterson_powerschool"
}

# KIPP TAF datasets
import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf"]
  id = "projects/teamster-332318/datasets/kipptaf"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_accounting"]
  id = "projects/teamster-332318/datasets/kipptaf_accounting"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_act"]
  id = "projects/teamster-332318/datasets/kipptaf_act"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_adp_payroll"]
  id = "projects/teamster-332318/datasets/kipptaf_adp_payroll"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_adp_workforce_manager"]
  id = "projects/teamster-332318/datasets/kipptaf_adp_workforce_manager"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_adp_workforce_now"]
  id = "projects/teamster-332318/datasets/kipptaf_adp_workforce_now"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_alchemer"]
  id = "projects/teamster-332318/datasets/kipptaf_alchemer"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_amplify"]
  id = "projects/teamster-332318/datasets/kipptaf_amplify"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_appsheet"]
  id = "projects/teamster-332318/datasets/kipptaf_appsheet"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_assessments"]
  id = "projects/teamster-332318/datasets/kipptaf_assessments"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_collegeboard"]
  id = "projects/teamster-332318/datasets/kipptaf_collegeboard"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_coupa"]
  id = "projects/teamster-332318/datasets/kipptaf_coupa"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_crdc"]
  id = "projects/teamster-332318/datasets/kipptaf_crdc"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_dayforce"]
  id = "projects/teamster-332318/datasets/kipptaf_dayforce"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_dbt_test__audit"]
  id = "projects/teamster-332318/datasets/kipptaf_dbt_test__audit"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_deanslist"]
  id = "projects/teamster-332318/datasets/kipptaf_deanslist"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_edplan"]
  id = "projects/teamster-332318/datasets/kipptaf_edplan"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_egencia"]
  id = "projects/teamster-332318/datasets/kipptaf_egencia"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_extracts"]
  id = "projects/teamster-332318/datasets/kipptaf_extracts"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_finalsite"]
  id = "projects/teamster-332318/datasets/kipptaf_finalsite"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_finance"]
  id = "projects/teamster-332318/datasets/kipptaf_finance"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_fldoe"]
  id = "projects/teamster-332318/datasets/kipptaf_fldoe"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_google_appsheet"]
  id = "projects/teamster-332318/datasets/kipptaf_google_appsheet"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_google_directory"]
  id = "projects/teamster-332318/datasets/kipptaf_google_directory"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_google_forms"]
  id = "projects/teamster-332318/datasets/kipptaf_google_forms"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_google_sheets"]
  id = "projects/teamster-332318/datasets/kipptaf_google_sheets"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_hubspot"]
  id = "projects/teamster-332318/datasets/kipptaf_hubspot"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_illuminate"]
  id = "projects/teamster-332318/datasets/kipptaf_illuminate"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_instagram_business"]
  id = "projects/teamster-332318/datasets/kipptaf_instagram_business"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_iready"]
  id = "projects/teamster-332318/datasets/kipptaf_iready"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_kippadb"]
  id = "projects/teamster-332318/datasets/kipptaf_kippadb"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_knowbe4"]
  id = "projects/teamster-332318/datasets/kipptaf_knowbe4"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_ldap"]
  id = "projects/teamster-332318/datasets/kipptaf_ldap"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_marts"]
  id = "projects/teamster-332318/datasets/kipptaf_marts"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_metrics"]
  id = "projects/teamster-332318/datasets/kipptaf_metrics"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_njdoe"]
  id = "projects/teamster-332318/datasets/kipptaf_njdoe"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_nsc"]
  id = "projects/teamster-332318/datasets/kipptaf_nsc"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_overgrad"]
  id = "projects/teamster-332318/datasets/kipptaf_overgrad"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_pearson"]
  id = "projects/teamster-332318/datasets/kipptaf_pearson"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_people"]
  id = "projects/teamster-332318/datasets/kipptaf_people"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_performance_management"]
  id = "projects/teamster-332318/datasets/kipptaf_performance_management"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_powerschool"]
  id = "projects/teamster-332318/datasets/kipptaf_powerschool"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_powerschool_enrollment"]
  id = "projects/teamster-332318/datasets/kipptaf_powerschool_enrollment"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_qa"]
  id = "projects/teamster-332318/datasets/kipptaf_qa"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_renlearn"]
  id = "projects/teamster-332318/datasets/kipptaf_renlearn"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_reporting"]
  id = "projects/teamster-332318/datasets/kipptaf_reporting"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_schoolmint_grow"]
  id = "projects/teamster-332318/datasets/kipptaf_schoolmint_grow"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_smartrecruiters"]
  id = "projects/teamster-332318/datasets/kipptaf_smartrecruiters"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_students"]
  id = "projects/teamster-332318/datasets/kipptaf_students"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_surveys"]
  id = "projects/teamster-332318/datasets/kipptaf_surveys"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_tableau"]
  id = "projects/teamster-332318/datasets/kipptaf_tableau"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_titan"]
  id = "projects/teamster-332318/datasets/kipptaf_titan"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_topline"]
  id = "projects/teamster-332318/datasets/kipptaf_topline"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_utils"]
  id = "projects/teamster-332318/datasets/kipptaf_utils"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["kipptaf_zendesk"]
  id = "projects/teamster-332318/datasets/kipptaf_zendesk"
}

# Other datasets
import {
  to = module.bigquery.google_bigquery_dataset.production["teamster_kipppaterson"]
  id = "projects/teamster-332318/datasets/teamster_kipppaterson"
}

import {
  to = module.bigquery.google_bigquery_dataset.production["topline_scratch"]
  id = "projects/teamster-332318/datasets/topline_scratch"
}

# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

import {
  to = module.github.github_actions_variable.gcp_project_id
  id = "teamster:GCP_PROJECT_ID"
}

import {
  to = module.github.github_actions_variable.gcp_project_number
  id = "teamster:GCP_PROJECT_NUMBER"
}

import {
  to = module.github.github_actions_variable.gcp_region
  id = "teamster:GCP_REGION"
}

import {
  to = module.github.github_actions_variable.dagster_organization_id
  id = "teamster:DAGSTER_ORGANIZATION_ID"
}
```

- [ ] **Step 4: Commit**

```bash
git add terraform/main.tf terraform/outputs.tf terraform/imports.tf
git commit -m "feat(terraform): add root module composition and import blocks"
```

---

## Task 11: terraform/README.md

**Files:**

- Create: `terraform/README.md`

- [ ] **Step 1: Create `terraform/README.md`**

```markdown
# Terraform

Infrastructure as code for the Teamster data platform.

For setup, usage, and module reference, see the
[Infrastructure documentation](https://teamschools.github.io/teamster/infrastructure/).
```

- [ ] **Step 2: Commit**

```bash
git add terraform/README.md
git commit -m "docs(terraform): add README pointer to MkDocs site"
```

---

## Task 12: MkDocs infrastructure documentation

**Files:**

- Create: `docs/infrastructure/index.md`
- Create: `docs/infrastructure/bootstrap.md`
- Create: `docs/infrastructure/operations.md`
- Create: `docs/infrastructure/modules.md`
- Modify: `mkdocs.yml` (add nav entry)

- [ ] **Step 1: Create `docs/infrastructure/index.md`**

````markdown
# Infrastructure

Teamster's infrastructure is codified in Terraform under `terraform/` at the
repository root. This section documents the architecture, setup, and day-to-day
operations.

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                    GitHub (TEAMSchools/teamster)             │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Branch       │  │ Actions      │  │ Secrets &         │  │
│  │ Protection   │  │ Workflows    │  │ Variables         │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────────────┘  │
│         │                 │ (OIDC)                           │
└─────────┼─────────────────┼─────────────────────────────────┘
          │                 │
          │    ┌────────────▼────────────┐
          │    │  Workload Identity      │
          │    │  Federation (IAM)       │
          │    └────────────┬────────────┘
          │                 │
┌─────────┼─────────────────┼─────────────────────────────────┐
│         │   GCP Project: teamster-332318                    │
│         │                 │                                  │
│  ┌──────▼───────┐  ┌─────▼──────────┐  ┌────────────────┐  │
│  │ Artifact     │  │ GKE Autopilot  │  │ BigQuery       │  │
│  │ Registry     │  │ (us-central1)  │  │ (700+ datasets)│  │
│  └──────────────┘  │                │  └────────────────┘  │
│                    │ ┌────────────┐ │                       │
│                    │ │ Dagster    │ │  ┌────────────────┐  │
│                    │ │ Cloud Agent│ │  │ Cloud Storage  │  │
│                    │ ├────────────┤ │  │ (6 buckets)    │  │
│                    │ │ 1Password  │ │  └────────────────┘  │
│                    │ │ Operator   │ │                       │
│                    │ └────────────┘ │                       │
│                    └────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```
````

## Modules

| Module               | What it manages                                                         |
| -------------------- | ----------------------------------------------------------------------- |
| `bootstrap/`         | GCS bucket for Terraform state (the only manually-created resource)     |
| `gke/`               | GKE Autopilot cluster                                                   |
| `gcs/`               | Cloud Storage buckets (one per code location + test)                    |
| `bigquery/`          | BigQuery production datasets + BigLake connection                       |
| `artifact_registry/` | Docker container image repository                                       |
| `iam/`               | Service accounts, Workload Identity Federation, IAM bindings            |
| `k8s/`               | Kubernetes namespace, Helm releases (Dagster + 1Password), secret items |
| `github/`            | Repository settings, branch protection, Actions secrets/variables       |

See [Module Reference](modules.md) for details on each module's variables and
outputs.

## Quick Start

1. [Bootstrap](bootstrap.md) — create the state bucket and import existing
   resources
2. [Day-to-Day Operations](operations.md) — make infrastructure changes via
   Terraform

````

- [ ] **Step 2: Create `docs/infrastructure/bootstrap.md`**

```markdown
# Bootstrap & Import

## Prerequisites

- [Terraform CLI](https://developer.hashicorp.com/terraform/install) >= 1.5.0
- `gcloud` CLI authenticated with permissions on `teamster-332318`
- A GitHub personal access token with `repo` scope (for the GitHub provider)
- Access to the GKE cluster (`gcloud container clusters get-credentials`)

## Step 1: Create the State Bucket

The state bucket is the one resource that must exist before Terraform can manage
anything else. The bootstrap module handles this with local state.

```bash
cd terraform/modules/bootstrap
terraform init
terraform plan
terraform apply
````

This creates `teamster-terraform-state` in `us-central1` with versioning
enabled.

## Step 2: Initialize the Root Module

```bash
cd ../../  # back to terraform/
terraform init
```

This configures the GCS backend and downloads all providers.

## Step 3: Import Existing Resources

The `imports.tf` file contains declarative `import` blocks for all existing
resources. On first apply, Terraform imports them into state:

```bash
terraform plan
```

Review the plan carefully. It should show imports and potentially some attribute
diffs where the `.tf` code doesn't perfectly match reality yet.

Iterate: adjust `.tf` files to match actual resource attributes, re-run
`terraform plan`, repeat until the plan shows no changes (aside from the imports
themselves).

```bash
terraform apply
```

!!! warning The first apply performs imports and may show diffs. Review each
change carefully — Terraform will modify real infrastructure to match the code.
Use `terraform plan` to preview all changes before applying.

## Step 4: Verify

```bash
terraform plan
```

A clean plan (no changes) confirms all resources are imported and the code
matches reality.

## Adapting for Another Organization

If you're forking this setup for a different school network:

1. Update `terraform.tfvars` with your GCP project, region, code locations, and
   GitHub org/repo
2. Remove or modify the `imports.tf` file (import blocks are specific to our
   resource IDs)
3. Run `terraform plan` to preview what will be created
4. Run `terraform apply` to create the infrastructure from scratch

````

- [ ] **Step 3: Create `docs/infrastructure/operations.md`**

```markdown
# Day-to-Day Operations

## Making Infrastructure Changes

1. Create a branch for the change
2. Edit the relevant `.tf` files
3. Run `terraform plan` from the `terraform/` directory:

    ```bash
    cd terraform
    terraform plan
    ```

4. Include the plan output in the PR description
5. After review and merge, apply from `main`:

    ```bash
    git checkout main && git pull
    cd terraform
    terraform apply
    ```

## Common Operations

### Add a New GCS Bucket for a Code Location

Add the location name to `code_locations` in `terraform.tfvars`:

```hcl
code_locations = ["kipptaf", "kippnewark", "kippcamden", "kippmiami", "kipppaterson", "newlocation"]
````

### Add a New BigQuery Dataset

Add the dataset to the `production_datasets` local in `main.tf`:

```hcl
"newlocation_source" = "New Location: source system"
```

### Add a New 1Password Item

Add the item to the `onepassword_items` local in
`terraform/modules/k8s/onepassword_items.tf`:

```hcl
"op-new-item" = "vaults/Data Team/items/New Item Name"
```

### Add a New GitHub Actions Secret or Variable

Add a resource to `terraform/modules/github/main.tf`.

## Authentication

### GCP

Terraform uses Application Default Credentials:

```bash
gcloud auth application-default login
```

### GitHub

Set the `GITHUB_TOKEN` environment variable:

```bash
export GITHUB_TOKEN="ghp_..."
```

Or use the `gh` CLI token:

```bash
export GITHUB_TOKEN=$(gh auth token)
```

### Kubernetes/Helm

The Kubernetes and Helm providers authenticate via the GKE cluster credentials
output by the `gke` module. Ensure you have `gcloud` configured for the project.

````

- [ ] **Step 4: Create `docs/infrastructure/modules.md`**

```markdown
# Module Reference

## `bootstrap/`

Creates the GCS bucket for Terraform remote state. This module uses local state
and is applied separately from the root module.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `project_id` | `string` | `teamster-332318` | GCP project ID |
| `region` | `string` | `us-central1` | Bucket location |

| Output | Description |
|--------|-------------|
| `bucket_name` | Name of the state bucket |

## `gke/`

Manages the GKE Autopilot cluster.

| Variable | Type | Description |
|----------|------|-------------|
| `project_id` | `string` | GCP project ID |
| `region` | `string` | Cluster region |
| `cluster_name` | `string` | Cluster name |

| Output | Description |
|--------|-------------|
| `cluster_endpoint` | Cluster API endpoint |
| `cluster_ca_certificate` | Base64-encoded CA cert (sensitive) |
| `cluster_name` | Cluster name |

## `gcs/`

Manages Cloud Storage buckets using `for_each` over code location names.

| Variable | Type | Description |
|----------|------|-------------|
| `project_id` | `string` | GCP project ID |
| `region` | `string` | Bucket location |
| `code_locations` | `list(string)` | Code location names |

| Output | Description |
|--------|-------------|
| `bucket_names` | Map of location key to bucket name |
| `bucket_urls` | Map of location key to `gs://` URL |

## `bigquery/`

Manages BigQuery production datasets and the BigLake external connection.

| Variable | Type | Description |
|----------|------|-------------|
| `project_id` | `string` | GCP project ID |
| `location` | `string` | Dataset/connection location |
| `production_datasets` | `map(string)` | Map of dataset_id to description |

| Output | Description |
|--------|-------------|
| `dataset_ids` | List of managed dataset IDs |
| `biglake_connection_name` | Fully-qualified BigLake connection name |

## `artifact_registry/`

Manages the Docker container image repository.

| Variable | Type | Description |
|----------|------|-------------|
| `project_id` | `string` | GCP project ID |
| `region` | `string` | Registry region |

| Output | Description |
|--------|-------------|
| `repository_id` | Repository ID |
| `repository_url` | Full Docker registry URL |

## `iam/`

Manages service accounts, Workload Identity Federation, and IAM role bindings.
Also documents Google Workspace domain-wide delegation.

| Variable | Type | Description |
|----------|------|-------------|
| `project_id` | `string` | GCP project ID |
| `project_number` | `string` | GCP project number |
| `region` | `string` | GCP region |
| `github_org` | `string` | GitHub organization |
| `github_repo` | `string` | GitHub repository |
| `artifact_registry_repository_id` | `string` | AR repo ID for IAM binding |

| Output | Description |
|--------|-------------|
| `dagster_agent_email` | Agent SA email |
| `dagster_agent_account_id` | Agent SA account ID |
| `workload_identity_pool_name` | WI pool name |
| `workload_identity_provider_name` | WI provider name |
| `workspace_delegation_client_id` | Client ID for admin console |

### Domain-Wide Delegation

After applying, configure domain-wide delegation in the Google Workspace admin
console:

1. Get the client ID: `terraform output workspace_delegation_client_id`
2. Go to **admin.google.com** > **Security** > **Access and data control** >
   **API controls** > **Domain-wide delegation** > **Add new**
3. Enter the client ID and authorize the OAuth scopes listed in
   `terraform/modules/iam/main.tf`

## `k8s/`

Manages everything on the GKE cluster: namespace, service account, Helm releases
(Dagster Cloud agent and 1Password Connect+Operator), and OnePasswordItem CRDs.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `project_id` | `string` | | GCP project ID |
| `dagster_agent_email` | `string` | | Agent SA email |
| `dagster_agent_account_id` | `string` | | Agent SA account ID |
| `namespace` | `string` | `dagster-cloud` | K8s namespace |

| Output | Description |
|--------|-------------|
| `namespace` | Namespace name |
| `dagster_agent_release_name` | Dagster Helm release name |
| `onepassword_release_name` | 1Password Helm release name |

## `github/`

Manages repository settings, branch protection, and GitHub Actions
secrets/variables.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `github_org` | `string` | | GitHub organization |
| `github_repo` | `string` | | Repository name |
| `gcp_project_id` | `string` | | For Actions variable |
| `gcp_project_number` | `string` | | For Actions variable |
| `gcp_region` | `string` | | For Actions variable |
| `dagster_organization_id` | `string` | `kipptaf` | For Actions variable |

| Output | Description |
|--------|-------------|
| `repository_full_name` | Full name (org/repo) |
````

- [ ] **Step 5: Add infrastructure section to `mkdocs.yml` nav**

Add this entry to the `nav:` list in `mkdocs.yml`, after the Reference section:

```yaml
- Infrastructure:
    - infrastructure/index.md
    - Bootstrap & Import: infrastructure/bootstrap.md
    - Day-to-Day Operations: infrastructure/operations.md
    - Module Reference: infrastructure/modules.md
```

- [ ] **Step 6: Commit**

```bash
git add terraform/README.md docs/infrastructure/ mkdocs.yml
git commit -m "docs: add infrastructure documentation to MkDocs site"
```

---

## Task 13: Delete replaced files

**Files:**

- Delete: `.gcloud/gh.sh`
- Delete: `.gcloud/k8s.sh`
- Delete: `.k8s/1password/install.sh`
- Delete: `.k8s/1password/items.yaml`
- Delete: `.k8s/1password/values-override.yaml`
- Delete: `.k8s/1password/values.yaml` (if present — auto-generated)
- Delete: `.k8s/dagster/install.sh`
- Delete: `.k8s/dagster/values-override.yaml`
- Delete: `.k8s/dagster/values.yaml` (if present — auto-generated)
- Delete: `.k8s/setup.sh`

- [ ] **Step 1: Remove `.gcloud/` directory**

```bash
git rm -r .gcloud/
```

- [ ] **Step 2: Remove `.k8s/` directory**

```bash
git rm -r .k8s/
```

- [ ] **Step 3: Clean up `.gitignore`**

Remove the `.k8s/get_helm.sh` entry from `.gitignore` (no longer relevant).

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "chore: remove .gcloud/ and .k8s/ replaced by terraform modules"
```

---

## Task 14: Final validation and reconciliation

This task is manual and iterative. It cannot be fully scripted because
`terraform plan` output depends on the actual state of GCP resources.

- [ ] **Step 1: Bootstrap the state bucket**

```bash
cd terraform/modules/bootstrap
terraform init
terraform plan
terraform apply
```

- [ ] **Step 2: Initialize root module**

```bash
cd ../../
terraform init
```

- [ ] **Step 3: Run `terraform plan` and iterate**

```bash
terraform plan
```

Review the output. For each resource showing drift:

1. Read the Terraform provider docs for that resource type
2. Add the missing/different attributes to the `.tf` file
3. Re-run `terraform plan`
4. Repeat until clean

The GKE cluster will likely need the most iterations — Autopilot clusters have
many computed attributes.

- [ ] **Step 4: Apply when plan is clean**

```bash
terraform apply
```

- [ ] **Step 5: Verify with a final plan**

```bash
terraform plan
```

Expected output: `No changes. Your infrastructure matches the configuration.`

- [ ] **Step 6: Commit the lock file and any reconciliation changes**

```bash
git add terraform/.terraform.lock.hcl
git add -u
git commit -m "feat(terraform): reconcile imported resources and lock providers"
```
