# 05. Artefacts, Images and Secrets

*Agents on AWS Lab, article 5 of 8*

`infra/storage.tf` holds the three stores the service depends on.

## S3: eval results

Lab 7's gates produce evidence: eval results and promotion decisions. That evidence belongs
somewhere durable and reviewable, which is the `eval-results/` prefix of a private bucket:

- **all four public-access blocks on**, and a negative control turns one off;
- **KMS encryption** by default, with bucket keys to cut KMS request costs;
- **TLS only**: a bucket policy denies any request where `aws:SecureTransport` is false;
- **versioning on**, so evidence can't be silently overwritten;
- **lifecycle rules**: results expire after `artifact_retention_days` (90 by default), and old
  versions after 30 days.

## ECR: the image

- **Immutable tags.** `d569c15` always means the same image. A deploy can't change underneath you,
  and a rollback goes back to exactly what ran before. A negative control flips the setting to
  `MUTABLE`.
- **Scan on push**, plus KMS encryption.
- **A lifecycle policy** that keeps the last 30 images.

## Secrets Manager: the model API key

```hcl
resource "aws_secretsmanager_secret" "anthropic_api_key" { ... }   # the container only
```

Terraform creates the secret but **never its value**. An `aws_secretsmanager_secret_version` with a
value would put the key in the Terraform code or variables, in plan output, and in the state file
in plaintext. A static check forbids that resource type. Set the value once, out of band:

```bash
aws secretsmanager put-secret-value --secret-id <api_key_secret_arn> --secret-string ...
```

## From Secrets Manager to the pod

The chart can render an `ExternalSecret`. The External Secrets Operator, using its own IRSA role,
reads the secret and keeps a Kubernetes Secret in sync. The pod reads it with `secretKeyRef`. The
key never appears in Helm values, Git or CI logs, and a chart test checks that no rendering ever
contains a `Secret` with data. The External Secrets path isn't exercised in CI; it needs a real
account, and article 08 lists it with the other next steps.
