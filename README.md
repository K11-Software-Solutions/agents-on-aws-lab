# Agents on AWS Lab

**Lab 8 of [Becoming an AI Engineer](https://github.com/K11-Software-Solutions/becoming-an-ai-engineer).**
Run lab 7's agent service on Kubernetes in AWS. This lab provides:
- **Terraform** for the network, an EKS cluster, IRSA, S3, ECR and Secrets Manager;
- a hardened **Helm** chart;
- tests that prove every policy can fail, **with no AWS account**: `terraform test` with a mocked
  provider, and rendered-manifest checks;
- a real deployment to a **kind** cluster in CI, gated by lab 7's eval and promotion gates. Real
  EKS is an optional, manual step.

## The AI Engineering series

| # | Lab | Status |
|---|---|---|
| 1 | [AI Engineering Foundations](https://github.com/K11-Software-Solutions/becoming-an-ai-engineer) | ✅ |
| 2 | [RAG Engineering Lab](https://github.com/K11-Software-Solutions/rag-engineering-lab) | ✅ |
| 3 | [Agent SDK Lab](https://github.com/K11-Software-Solutions/agent-sdk-lab) | ✅ |
| 4 | [MCP Server Engineering Lab](https://github.com/K11-Software-Solutions/mcp-server-engineering-lab) | ✅ |
| 5 | [AI Coding Assistant Extensions Lab](https://github.com/K11-Software-Solutions/coding-assistant-extensions-lab) | ✅ |
| 6 | [PDLC Agents Lab](https://github.com/K11-Software-Solutions/pdlc-agents-lab) | ✅ |
| 7 | [Shipping Agents Lab](https://github.com/K11-Software-Solutions/shipping-agents-lab) | ✅ |
| 8 | **Agents on AWS Lab** (this repo) | ✅ |
| 9 | Operating Agents Lab | planned |

## What gets built

```text
VPC (2 AZs) ── public subnets: NAT, load balancers
            └─ private subnets: EKS nodes (no public IPs)
EKS ── API endpoint: private, plus public limited to admin_cidrs
    ├─ Kubernetes secrets encrypted with a KMS key; audit logs on; access entries (no aws-auth)
    └─ pod "kestrel-agents" ── IRSA role ── S3 eval-results/* (read/write)
                                         ├─ one Secrets Manager secret (read)
                                         └─ the KMS key (decrypt)
ECR: immutable tags, scan on push        S3: private, KMS, TLS-only, versioned, 90-day expiry
```

## Gates

| Job | What it proves | Needs |
|---|---|---|
| terraform | `fmt`, `validate`, and `terraform test`: 5 policy runs plus 3 rejected-input runs | nothing (mocked AWS) |
| policy | `helm lint --strict`; 16 checks on rendered manifests; 3 static HCL checks; **7 negative controls**, each breaking the Terraform one way and requiring `terraform test` to fail | nothing |
| kind | builds lab 7's image at a pinned commit; installs the chart; checks the uid and the read-only filesystem; **lab 7's eval gate through the Service**; a rolling upgrade to a shadow rollout; the **promotion gate on the pods' logs** | Docker (GitHub runner) |
| eks-plan | `terraform plan` against a real account through GitHub OIDC (no stored AWS keys) | manual; `AWS_PLAN_ROLE_ARN` and `TF_STATE_BUCKET` repository variables |

## Run it

The tests need Terraform ≥ 1.9 (developed with 1.17.2) and Helm 4 (v4.3.2):

```bash
terraform -chdir=infra init -backend=false
```

```bash
terraform -chdir=infra test
```

```bash
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
```

```bash
pytest
```

```bash
helm template kestrel charts/kestrel-agents -f charts/values/eks.yaml
```

### Deploying for real (costs money)

1. `terraform -chdir=infra init -backend-config=...` and `terraform apply -var='admin_cidrs=["<your network>/32"]'`.
2. Set the API key's value once:
   `aws secretsmanager put-secret-value --secret-id <api_key_secret_arn> --secret-string ...`.
3. Push lab 7's image to `ecr_repository_url` with an immutable tag.
4. Install the External Secrets Operator with a `ClusterSecretStore` named `aws-secrets-manager`.
5. Put the Terraform outputs in your values (see `charts/values/eks.yaml`), then
   `helm install kestrel charts/kestrel-agents -n kestrel --create-namespace -f your-values.yaml`.

An EKS control plane, two `t3.large` nodes and a NAT gateway cost money every hour they exist.
`terraform destroy` when you're done.

## Verified, and not

- **Verified:** Terraform `fmt`/`validate`/`test`, `helm lint` and template, and all pytest checks,
  locally with Terraform 1.17.2 and Helm v4.3.2. The kind deployment runs in CI.
- **Not verified:** `terraform apply` against a real AWS account, and the External Secrets path.
  The mocked tests check the configuration, not AWS's behaviour.

## Layout

| Path | What it is |
|---|---|
| [infra/](infra) | Terraform: network, EKS, IRSA, storage, outputs |
| [infra/tests/infra.tftest.hcl](infra/tests/infra.tftest.hcl) | `terraform test` with a mocked AWS provider |
| [charts/kestrel-agents/](charts/kestrel-agents) | The Helm chart |
| [charts/values/](charts/values) | Example values for EKS and for kind |
| [tests/](tests) | Rendered-manifest checks, static HCL checks, Terraform negative controls |

## Articles

| # | Article |
|---|---|
| 01 | [From a Container to a Cluster](articles/01-from-container-to-cluster.md) |
| 02 | [The Network](articles/02-the-network.md) |
| 03 | [A Locked-Down EKS Cluster](articles/03-a-locked-down-eks-cluster.md) |
| 04 | [IRSA: AWS Credentials Without Keys](articles/04-irsa.md) |
| 05 | [Artefacts, Images and Secrets](articles/05-artefacts-images-and-secrets.md) |
| 06 | [Testing Infrastructure Without an AWS Account](articles/06-testing-infrastructure.md) |
| 07 | [The Helm Chart](articles/07-the-helm-chart.md) |
| 08 | [kind in CI, Real EKS, and What Comes Next](articles/08-kind-eks-and-next.md) |

## Licence and citation

Code: [MIT](LICENSE). Articles: [CC BY 4.0](articles/LICENSE.md). Cite with [CITATION.cff](CITATION.cff).
Kestrel Labs is fictional. Account ids and ARNs in examples are AWS's documentation placeholders.
