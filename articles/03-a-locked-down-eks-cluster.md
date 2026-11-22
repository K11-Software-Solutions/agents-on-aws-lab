# 03. A Locked-Down EKS Cluster

*Agents on AWS Lab, article 3 of 8*

`infra/eks.tf` creates the cluster, a managed node group and the OIDC provider. Most of its lines
take access away.

| Setting | Why |
|---|---|
| `endpoint_private_access = true` | nodes and in-VPC tools reach the API privately |
| `public_access_cidrs = var.admin_cidrs` | the public API endpoint answers only your networks |
| `encryption_config { resources = ["secrets"] }` | Kubernetes Secrets are encrypted with your KMS key, not just at rest by default |
| `enabled_cluster_log_types = ["api", "audit", "authenticator"]` | who did what to the cluster, in CloudWatch |
| `access_config { authentication_mode = "API" }` | EKS access entries instead of the old `aws-auth` ConfigMap |
| nodes in private subnets | no inbound path from the internet |
| `AL2023_x86_64_STANDARD` | a current, supported node image |

## The endpoint can't be opened by accident

```hcl
validation {
  condition     = length(var.admin_cidrs) > 0 && !contains(var.admin_cidrs, "0.0.0.0/0")
  error_message = "admin_cidrs must list specific networks; 0.0.0.0/0 would expose the API endpoint..."
}
```

`admin_cidrs` has no default, so you must choose. A `terraform test` run passes `0.0.0.0/0` and
expects the plan to fail. A negative control hard-codes `0.0.0.0/0` into the cluster itself and
expects the policy test to catch it.

## One key, rotated

A single customer-managed KMS key with rotation on encrypts cluster secrets, control-plane logs,
S3 artefacts, ECR images and the Secrets Manager secret. One key is simpler to reason about for a
lab. Larger estates often use one key per data class, so access can be split.

## What's left for you

Pin `kubernetes_version` and upgrade on a schedule; EKS versions reach end of support. Add the add-ons
you need (AWS load balancer controller, External Secrets, metrics server). Each is a Helm chart
with its own IRSA role.
