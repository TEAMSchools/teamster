# CLAUDE.md — `.k8s/`

Helm overrides and deploy scripts for Dagster Cloud agent and 1Password Connect
on GKE Autopilot.

## Conventions

- `values.yaml` is auto-downloaded from Helm — never edit. All customizations go
  in `values-override.yaml`.
- `safe-to-evict: "false"` only blocks cluster autoscaler evictions — kubelet
  node-pressure evictions (exit 137, OOM) are unaffected. Scale-Out density
  makes these occasional; Dagster retries automatically.
- GKE Autopilot cluster: `autopilot-cluster-dagster-hybrid-1` in `us-central1`
  (`kubectl config current-context`).
- Spot VMs are a **preference** on agent and code server pods — falls back to
  on-demand during GCE STOCKOUT. Run pods are on-demand only
  (`safe-to-evict: "false"` + spot tolerations are mutually exclusive on
  Autopilot). `arm64` requires an explicit `compute-class` in `nodeSelector`.
