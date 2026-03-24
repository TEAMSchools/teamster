# CLAUDE.md — `.k8s/`

Helm charts and scripts for deploying the Dagster Cloud agent and 1Password
Connect to GKE.

## Directory Structure

```text
.k8s/
├── setup.sh                   # Bootstrap kubectl, Helm, gke-mcp
├── dagster/
│   ├── install.sh             # Deploy Dagster Cloud agent via Helm
│   ├── values.yaml            # Downloaded Helm defaults — do not edit
│   └── values-override.yaml   # Custom overrides (edit this)
└── 1password/
    ├── install.sh             # Deploy 1Password Connect via Helm
    ├── values.yaml            # Downloaded Helm defaults — do not edit
    ├── values-override.yaml   # Custom overrides (edit this)
    └── items.yaml             # 1Password secret items to sync
```

## Setup

Run in order:

1. `bash .k8s/setup.sh` — installs kubectl, Helm to `~/.local/bin`, gke-mcp,
   creates `dagster-cloud` namespace
2. `bash .k8s/dagster/install.sh` — deploys Dagster Cloud agent
3. `bash .k8s/1password/install.sh` — deploys 1Password Connect (requires
   `OP_CONNECT_TOKEN` in `env/.env`)

## Conventions

- **`values.yaml`** is auto-downloaded from Helm — never edit it; it will be
  overwritten. All customizations go in `values-override.yaml`.
- **Helm installs to `~/.local/bin`** to avoid `/usr/local/bin` permission
  issues (no `sudo`).
- **gke-mcp binary** includes sha256 checksum verification — `setup.sh` exits on
  mismatch.
