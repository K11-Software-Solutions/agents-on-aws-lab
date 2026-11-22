# 06. Testing Infrastructure Without an AWS Account

*Agents on AWS Lab, article 6 of 8*

Infrastructure code is code, and it can be tested before anything exists. This lab uses three
layers.

## 1. `terraform test` with a mocked provider

```hcl
mock_provider "aws" {
  override_resource {
    target = aws_eks_cluster.this
    values = { identity = [{ oidc = [{ issuer = "https://oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE..." }] }] }
  }
}

run "irsa_trusts_one_service_account" {
  command = apply
  assert {
    condition     = jsondecode(aws_iam_role.app.assume_role_policy).Statement[0].Condition.StringEquals[...] == "system:serviceaccount:kestrel:kestrel-agents"
    error_message = "the app role must trust exactly the kestrel/kestrel-agents service account"
  }
}
```

The mock provider fakes every AWS call. `command = apply` against a mock creates nothing and needs
no credentials, but computed values (ids, ARNs) get filled in, so assertions can inspect the
finished configuration. Overrides give the few values other resources parse, such as the OIDC
issuer, a realistic shape.

Policies are written with `jsonencode()` rather than `aws_iam_policy_document` data sources. A
mocked data source returns random text, so its JSON couldn't be asserted on.

The suite has 5 policy runs and 3 `expect_failures` runs, which check that bad inputs (an open API
endpoint, one AZ, impossible scaling) are refused.

## 2. Static checks on the HCL

`tests/test_infra.py` parses the `.tf` files with `python-hcl2` and checks:

- **forbidden resource types:** IAM users, access keys, secret values, ad-hoc security group rules;
- **literals:** no key-like strings and no `0.0.0.0/0` in access lists;
- **an allow-list of resource kinds,** so adding a new kind of resource is a deliberate, reviewed
  change.

## 3. Negative controls for the policy tests

The most important layer. Each control copies `infra/`, breaks one thing, runs `terraform test`
and requires it to **fail with the right message**:

| Breakage | Caught by |
|---|---|
| ECR tags mutable | storage run |
| one S3 public-access block off | storage run |
| `secretsmanager:*` in the app policy | least-privilege run |
| IRSA trusts `system:serviceaccount:*` | IRSA run |
| audit logs off | cluster run |
| API endpoint open to `0.0.0.0/0` | cluster run |
| public subnets hand out IPs | network run |

They reuse the initialised providers through `TF_DATA_DIR`, so all seven run in under a minute.

## What mocks can't tell you

Mocks check your configuration against your policy. They don't check that AWS accepts it: quotas,
service-linked roles, region availability, IAM propagation delays. The manual `eks-plan` job runs
a real plan, and only `apply` in a sandbox account proves the rest.
