# Terraform Infrastructure as Code

**Date:** 2026-03-30 **Status:** Draft **Motivation:** Reproducibility,
documentation, drift detection, change management

## Overview

Adopt Terraform to codify the Teamster project's GCP infrastructure as a
module-per-domain monorepo setup. The Terraform code lives in `terraform/` at
the repo root, with documentation published to the MkDocs site under
`docs/infrastructure/`. This replaces the existing `.gcloud/` and `.k8s/` shell
scripts with declarative, importable, and version-controlled infrastructure
definitions.

### Goals

1. **Reproducibility** -- if the GCP project were lost, the Terraform code
   provides a complete blueprint to rebuild it.
2. **Documentation** -- new team members and peer organizations can read the
   Terraform modules to understand exactly what infrastructure exists and how
   it's configured.
3. **Drift detection** -- `terraform plan` reveals when real infrastructure
   diverges from the declared state.
4. **Change management** -- infrastructure changes go through PR review like
   application code.

### Non-goals

- Fully automated CI/CD for Terraform (run locally for now).
- Managing Google Workspace admin console settings (documented manually).
- Managing the 1Password vault/item configuration (1Password side only).
- Managing Dagster Cloud API configuration (handled by `dagster-cloud.yaml`).

## Architecture

### Directory Structure

```
terraform/
  backend.tf             # GCS remote state configuration
  main.tf                # root module -- composes all child modules
  variables.tf           # project-level input variables
  outputs.tf             # key outputs (cluster endpoint, bucket names, etc.)
  providers.tf           # google, google-beta, kubernetes, github
  terraform.tfvars       # default variable values
  .terraform.lock.hcl    # provider version lock (committed to git)

  modules/
    bootstrap/           # GCS bucket for Terraform state (local state)
    gke/                 # GKE Autopilot cluster
    gcs/                 # Cloud Storage buckets
    bigquery/            # BigQuery datasets + BigLake connection
    artifact_registry/   # Container image repository
    iam/                 # Service accounts, Workload Identity, role bindings
    k8s/                 # Kubernetes namespace, Helm releases, 1Password items
    github/              # Repository settings, branch protection, Actions secrets
```

### Provider Configuration

| Provider      | Source                  | Purpose                            |
| ------------- | ----------------------- | ---------------------------------- |
| `google`      | `hashicorp/google`      | Core GCP resources                 |
| `google-beta` | `hashicorp/google-beta` | Beta GCP features (if needed)      |
| `kubernetes`  | `hashicorp/kubernetes`  | GKE cluster resources              |
| `github`      | `integrations/github`   | Repository and CI/CD configuration |

### Remote State

- **Backend:** GCS bucket (`teamster-terraform-state` in `us-central1`)
- **Locking:** GCS-native object locking
- **Bootstrap:** The state bucket is the one manually-created resource, managed
  by `modules/bootstrap/` with local state
- **`.gitignore` additions:** `*.tfstate`, `*.tfstate.backup`, `.terraform/`

## Module Specifications

### `bootstrap/`

Creates the GCS bucket that holds Terraform state for all other modules. This is
the only module that uses local state.

| Resource                | Name                       |
| ----------------------- | -------------------------- |
| `google_storage_bucket` | `teamster-terraform-state` |

Configuration: versioning enabled, `us-central1` location, uniform bucket-level
access.

### `gke/`

Manages the GKE Autopilot cluster that hosts Dagster Cloud workloads.

| Resource                   | Details                                                             |
| -------------------------- | ------------------------------------------------------------------- |
| `google_container_cluster` | `autopilot-cluster-dagster-hybrid-1`, Autopilot mode, `us-central1` |

Outputs: cluster endpoint, CA certificate, cluster name (consumed by `k8s/`
module and the `kubernetes` provider).

### `gcs/`

Manages Cloud Storage buckets using `for_each` over a list of code location
names.

| Resource                | Instances                                                                                                                        |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `google_storage_bucket` | `teamster-kipptaf`, `teamster-kippnewark`, `teamster-kippcamden`, `teamster-kippmiami`, `teamster-kipppaterson`, `teamster-test` |

### `bigquery/`

Manages BigQuery datasets and the BigLake external connection.

| Resource                     | Details                                      |
| ---------------------------- | -------------------------------------------- |
| `google_bigquery_dataset`    | Datasets per code location and source system |
| `google_bigquery_connection` | `biglake-teamster-gcs` in `us` location      |

The full list of datasets will be enumerated during implementation by querying
the existing BigQuery project.

### `artifact_registry/`

Manages the Docker image repository for CI/CD.

| Resource                              | Details                                       |
| ------------------------------------- | --------------------------------------------- |
| `google_artifact_registry_repository` | `teamster` repo, Docker format, `us-central1` |

### `iam/`

Manages service accounts, Workload Identity Federation, and IAM role bindings.
Also documents domain-wide delegation for Google Workspace APIs.

| Resource                                         | Details                                                                                                     |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------- |
| `google_iam_workload_identity_pool`              | `github` pool (GitHub Actions OIDC)                                                                         |
| `google_iam_workload_identity_pool_provider`     | `teamster` provider, issuer `token.actions.githubusercontent.com`, attribute condition on `TEAMSchools` org |
| `google_service_account`                         | `user-cloud-dagster-cloud-agent` (Dagster/GKE workload identity)                                            |
| `google_service_account`                         | Workspace API delegation SA (if separate)                                                                   |
| `google_project_iam_member`                      | Role bindings (e.g., `roles/storage.admin`)                                                                 |
| `google_service_account_iam_member`              | GKE workload identity binding                                                                               |
| `google_artifact_registry_repository_iam_member` | CI/CD push access (`roles/artifactregistry.repoAdmin`)                                                      |

**Domain-wide delegation documentation:**

The IAM module outputs the service account's `unique_id` (client ID). A `locals`
block documents the exact OAuth scopes and manual admin console steps required:

1. Navigate to admin.google.com > Security > API Controls > Domain-wide
   Delegation
2. Add the client ID from `terraform output workspace_delegation_client_id`
3. Authorize the following scopes:
   - `https://www.googleapis.com/auth/admin.directory.user`
   - `https://www.googleapis.com/auth/admin.directory.group`
   - (full scope list to be enumerated during implementation)

This ensures the Workspace delegation config is reproducible even though the
admin console step cannot be automated.

### `k8s/`

Manages everything that runs on the GKE cluster: namespace, service accounts,
Helm releases (Dagster agent and 1Password Operator), and 1Password item
mappings.

| Resource                     | Details                                                                   |
| ---------------------------- | ------------------------------------------------------------------------- |
| `kubernetes_namespace`       | `dagster-cloud`                                                           |
| `kubernetes_service_account` | Dagster agent SA with GKE workload identity annotation                    |
| `helm_release`               | Dagster Cloud agent (chart version + values override)                     |
| `helm_release`               | 1Password Connect + Operator                                              |
| `kubernetes_manifest`        | `OnePasswordItem` CRDs for secret sync (from `.k8s/1password/items.yaml`) |

Depends on the `gke/` module for cluster authentication.

### `github/`

Manages repository settings and CI/CD configuration.

| Resource                   | Details                                                                    |
| -------------------------- | -------------------------------------------------------------------------- |
| `github_repository`        | `teamster` repo settings (default branch, merge strategy, feature toggles) |
| `github_branch_protection` | `main` branch protection rules                                             |
| `github_actions_secret`    | `GCP_PROJECT_ID`, `GCP_PROJECT_NUMBER`, `DAGSTER_ORGANIZATION_ID`, etc.    |
| `github_actions_variable`  | Non-sensitive CI variables                                                 |

## Import Strategy

All resources are pre-existing. The migration approach is write-then-import:
write `.tf` files to match current state, then `terraform import` each resource.
A successful `terraform plan` showing "No changes" confirms the code matches
reality.

### Import order

Dependencies determine the order:

1. `iam/` -- service accounts, Workload Identity Federation (no dependencies)
2. `artifact_registry/` -- container repo (no dependencies)
3. `gcs/` -- storage buckets (no dependencies)
4. `bigquery/` -- datasets, BigLake connection (no dependencies)
5. `gke/` -- Autopilot cluster (no dependencies on other modules)
6. `k8s/` -- namespace, Helm releases, 1Password items (depends on `gke/`)
7. `github/` -- repo settings, secrets, branch protection (no GCP dependencies)

Steps 1-5 and 7 are independent. Step 6 must follow step 5.

After each import, run `terraform plan` and adjust `.tf` files until the plan
shows no changes.

### Import method

Terraform supports two import approaches:

- **`terraform import` CLI command** -- imperative, one resource at a time
- **`import` blocks in `.tf` files** (Terraform 1.5+) -- declarative, can be
  committed and run as part of `terraform apply`

The implementation should use `import` blocks where possible, as they are
self-documenting and reviewable in PRs.

## Day-to-Day Workflow

1. Create a branch for the infrastructure change
2. Modify the relevant `.tf` files
3. Run `terraform plan` and include the output in the PR description
4. Review the plan, merge the PR
5. Run `terraform apply` from the `main` branch

No CI/CD automation for Terraform initially. All plan/apply runs happen from a
developer machine with appropriate GCP and GitHub credentials.

## Files Deleted After Migration

| Path              | Replaced by                                           |
| ----------------- | ----------------------------------------------------- |
| `.gcloud/gh.sh`   | `terraform/modules/iam/`                              |
| `.gcloud/k8s.sh`  | `terraform/modules/iam/` + `terraform/modules/k8s/`   |
| `.k8s/1password/` | `terraform/modules/k8s/`                              |
| `.k8s/dagster/`   | `terraform/modules/k8s/`                              |
| `.k8s/setup.sh`   | No longer needed (Terraform providers handle tooling) |

The `.gcloud/` and `.k8s/` directories can be removed entirely.

## Documentation

Documentation lives in the MkDocs site under `docs/infrastructure/`, not as a
standalone README.

### Site pages

- **Architecture overview** -- text-based diagram showing the relationship
  between GCP, GKE, GitHub, 1Password, and Dagster Cloud
- **Prerequisites** -- GCP project, `gcloud` CLI, Terraform CLI, GitHub token,
  required IAM permissions
- **Bootstrap guide** -- step-by-step from zero to working state bucket
- **Import guide** -- how to import existing resources (adaptable for other
  orgs)
- **Day-to-day operations** -- how to make changes, run plan/apply
- **Module reference** -- what each module manages and its key variables/outputs

### `terraform/README.md`

Minimal pointer: "See the [Infrastructure documentation](link) for setup and
usage."

## Terraform Version

Require Terraform >= 1.5.0 (for `import` block support). Pin the constraint in
`terraform/versions.tf` via a `required_version` setting. Provider versions
pinned in `.terraform.lock.hcl` (committed to git).

## Key Variables

| Variable            | Value                                                                  | Description                          |
| ------------------- | ---------------------------------------------------------------------- | ------------------------------------ |
| `project_id`        | `teamster-332318`                                                      | GCP project ID                       |
| `project_number`    | `624231820004`                                                         | GCP project number                   |
| `region`            | `us-central1`                                                          | Default GCP region                   |
| `code_locations`    | `["kipptaf", "kippnewark", "kippcamden", "kippmiami", "kipppaterson"]` | Dagster code locations               |
| `github_org`        | `TEAMSchools`                                                          | GitHub organization                  |
| `github_repo`       | `teamster`                                                             | GitHub repository name               |
| `gke_cluster_name`  | `autopilot-cluster-dagster-hybrid-1`                                   | GKE cluster name                     |
| `bigquery_location` | `us`                                                                   | BigQuery dataset/connection location |
