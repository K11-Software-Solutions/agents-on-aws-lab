# 04. IRSA: AWS Credentials Without Keys

*Agents on AWS Lab, article 4 of 8*

The agent pods need to write eval results to S3 and read the model API key from Secrets Manager.
The worst way is an access key in an environment variable: long-lived, copyable, and shared by
everything that can read the pod spec.

IAM Roles for Service Accounts (IRSA) avoid keys entirely:

1. EKS publishes an **OIDC issuer**; Terraform registers it with IAM (`aws_iam_openid_connect_provider`).
2. Kubernetes gives each pod a signed token that says which **service account** it runs as.
3. The AWS SDK exchanges that token for **short-lived credentials** for a role, if the role's trust
   policy accepts it.

## Trust exactly one service account

```hcl
Condition = {
  StringEquals = {
    "${local.oidc_host}:sub" = "system:serviceaccount:${var.app_namespace}:${var.app_service_account}"
    "${local.oidc_host}:aud" = "sts.amazonaws.com"
  }
}
```

Without the `sub` condition, any pod in the cluster could assume the role. Two `terraform test`
assertions check the exact `sub` and `aud` values, and a negative control widens `sub` to
`system:serviceaccount:*` to prove they catch it.

## Least privilege

| Permission | Scope |
|---|---|
| `s3:PutObject`, `s3:GetObject` | `<bucket>/eval-results/*` only |
| `s3:ListBucket` | the bucket, with a `s3:prefix` condition of `eval-results/*` |
| `secretsmanager:GetSecretValue` | one secret's ARN |
| `kms:Decrypt`, `kms:GenerateDataKey` | the one key |

The policy test rejects any `*` in an action and any `"*"` resource. A negative control changes
`secretsmanager:GetSecretValue` to `secretsmanager:*`.

## The chart and the Terraform must agree

The role trusts `kestrel/kestrel-agents`. If the chart named its service account anything else,
IRSA would fail quietly at run time and the pod would get no credentials. A pytest test reads the
Terraform defaults and checks that the chart renders the same name, and that CI deploys into the
same namespace.

## In the chart

```yaml
serviceAccount:
  name: kestrel-agents
  roleArn: arn:aws:iam::111122223333:role/kestrel-dev-agents   # terraform output app_role_arn
```

With no `roleArn`, as on kind, the pod gets no annotation and no service-account token at all.
