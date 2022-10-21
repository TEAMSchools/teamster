# teamster-core

Next-gen data orchestration, powered by Dagster

- Docker container featuring core ops, graphs, and resources
- [Private GKE Autopilot](https://cloud.google.com/kubernetes-engine/docs/how-to/private-clusters#public_cp)
  cluster
- [Cloud NAT](https://cloud.google.com/nat/docs/gke-example#create-nat) provided static external IP
  for the cluster
- [Google Artifact Registry](https://cloud.google.com/artifact-registry/docs/docker/store-docker-container-images)
- Google Cloud services access prodivded by
  [Workload Identity](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity#authenticating_to)
- GitHub Actions for CI/CD
- [PDM](https://pdm.fming.dev/) for dependency management and deployment scripts

## Getting Started

1. Create a new repository from teamster-template
2. Clone new repository to dev environment
3. `pdm run teamster-init`
4. Fill in the required block of variables in `env/.env`
5. `pdm run teamster-post-init`
