# teamster

[![pdm-managed](https://img.shields.io/badge/pdm-managed-blueviolet)](https://pdm.fming.dev)
[![Trunk](https://img.shields.io/badge/trunk.io-enabled-brightgreen?logo=data:image/svg%2bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIGZpbGw9Im5vbmUiIHN0cm9rZT0iI0ZGRiIgc3Ryb2tlLXdpZHRoPSIxMSIgdmlld0JveD0iMCAwIDEwMSAxMDEiPjxwYXRoIGQ9Ik01MC41IDk1LjVhNDUgNDUgMCAxIDAtNDUtNDVtNDUtMzBhMzAgMzAgMCAwIDAtMzAgMzBtNDUgMGExNSAxNSAwIDAgMC0zMCAwIi8+PC9zdmc+)](https://trunk.io)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](code_of_conduct.md)

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
