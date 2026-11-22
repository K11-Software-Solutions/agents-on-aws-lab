# 01. From a Container to a Cluster

*Agents on AWS Lab, article 1 of 8*

Lab 7 ended with a hardened image and a pipeline that gates it. Running that image for a whole
company needs a place to run it, a way to give it credentials, and a way to update it without
downtime. That place is Kubernetes on AWS (EKS), described in two kinds of code:

| Concern | Tool | Lives in |
|---|---|---|
| network, cluster, IAM, storage, registry, secrets | Terraform | `infra/` |
| how the service runs in the cluster | Helm | `charts/kestrel-agents/` |

## What maps to what

| Lab 7 concept | In the cluster |
|---|---|
| `/healthz`, `/readyz` | liveness, readiness and startup probes |
| `--read-only --tmpfs /tmp` | `readOnlyRootFilesystem: true` with an `emptyDir` at `/tmp` |
| `--cap-drop ALL`, non-root user | the pod and container `securityContext` |
| `ANTHROPIC_API_KEY` from the environment | a Kubernetes Secret, synced from AWS Secrets Manager |
| `SHADOW_PERCENT`, `CANDIDATE_*` | Helm values, rendered into a ConfigMap |
| the eval and promotion gates | run against the deployed Service in CI |

## Testable without an AWS bill

An EKS cluster costs money every hour it exists. So most of this lab is tested without one:

- `terraform test` with a **mocked AWS provider** checks the planned resources against policy;
- **rendered Helm manifests** are checked in pytest;
- the chart is **really deployed** to a kind cluster (Kubernetes in Docker) on the CI runner, and
  lab 7's gates run against it;
- a real `terraform plan` against AWS is a manual, optional job.

Each layer gets its own article.
