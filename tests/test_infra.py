"""Static policy checks on the Terraform, and negative controls for `terraform test`.

The static checks parse the HCL directly (fast, no Terraform needed). The negative controls copy
the configuration, break one thing, and require `terraform test` to fail: a policy test that
can't fail proves nothing. They need terraform on PATH (or TERRAFORM=/path) and a prior
`terraform init` in infra/.
"""
import os
import shutil
import subprocess
from pathlib import Path

import hcl2
import pytest

INFRA = Path(__file__).resolve().parents[1] / "infra"
TERRAFORM = os.environ.get("TERRAFORM") or shutil.which("terraform")


def resources() -> list[tuple[str, str, dict]]:
    out = []
    for f in sorted(INFRA.glob("*.tf")):
        for block in hcl2.loads(f.read_text(encoding="utf-8")).get("resource", []):
            for rtype, named in block.items():
                for name, body in named.items():
                    out.append((rtype.strip('"'), name.strip('"'), body))
    return out


FORBIDDEN = {
    "aws_iam_user": "humans and CI use roles, not IAM users",
    "aws_iam_access_key": "long-lived access keys are never created",
    "aws_secretsmanager_secret_version": "secret values stay out of Terraform code and state",
    "aws_security_group_rule": "no ad-hoc security group rules",
}


def test_no_forbidden_resource_types():
    found = [(t, n) for t, n, _ in resources() if t in FORBIDDEN]
    assert not found, [f"{t}.{n}: {FORBIDDEN[t]}" for t, n in found]


def test_no_literal_secrets_or_open_cidrs_in_code():
    for f in INFRA.glob("*.tf"):
        text = f.read_text(encoding="utf-8")
        assert "sk-ant-" not in text and "AKIA" not in text, f.name
        for line in text.splitlines():
            if "public_access_cidrs" in line or "cidr_blocks" in line:
                assert "0.0.0.0/0" not in line, f"{f.name}: {line.strip()}"


def test_every_resource_is_one_of_the_expected_kinds():
    """New resource types should be a deliberate, reviewed change."""
    kinds = {t for t, _, _ in resources()}
    assert kinds <= {
        "aws_vpc", "aws_internet_gateway", "aws_subnet", "aws_eip", "aws_nat_gateway", "aws_route_table",
        "aws_route_table_association", "aws_kms_key", "aws_kms_alias", "aws_iam_role", "aws_iam_role_policy_attachment",
        "aws_cloudwatch_log_group", "aws_eks_cluster", "aws_eks_node_group", "aws_iam_openid_connect_provider",
        "aws_iam_role_policy", "aws_s3_bucket", "aws_s3_bucket_public_access_block", "aws_s3_bucket_versioning",
        "aws_s3_bucket_server_side_encryption_configuration", "aws_s3_bucket_lifecycle_configuration",
        "aws_s3_bucket_policy", "aws_ecr_repository", "aws_ecr_lifecycle_policy", "aws_secretsmanager_secret"}, kinds


# --- negative controls for terraform test ------------------------------------------------------

BREAKAGES = [
    ("storage.tf", 'image_tag_mutability = "IMMUTABLE"', 'image_tag_mutability = "MUTABLE"', "image tags must be immutable"),
    ("storage.tf", "restrict_public_buckets = true", "restrict_public_buckets = false", "public-access blocks"),
    ("irsa.tf", 'Action   = ["secretsmanager:GetSecretValue"]', 'Action   = ["secretsmanager:*"]', "no wildcard actions"),
    ("irsa.tf", '"system:serviceaccount:${var.app_namespace}:${var.app_service_account}"', '"system:serviceaccount:*"', "exactly the kestrel/kestrel-agents"),
    ("eks.tf", 'enabled_cluster_log_types = ["api", "audit", "authenticator"]', 'enabled_cluster_log_types = ["api"]', "audit logs"),
    ("eks.tf", "public_access_cidrs     = var.admin_cidrs", 'public_access_cidrs     = ["0.0.0.0/0"]', "limited to admin_cidrs"),
    ("network.tf", "map_public_ip_on_launch = false", "map_public_ip_on_launch = true", "must not hand out public IPs"),
]


@pytest.mark.skipif(not TERRAFORM or not (INFRA / ".terraform").exists(), reason="terraform not installed or not initialised")
@pytest.mark.parametrize("file, old, new, expected", BREAKAGES, ids=[b[3] for b in BREAKAGES])
def test_terraform_test_catches(tmp_path, file, old, new, expected):
    work = tmp_path / "infra"
    shutil.copytree(INFRA, work, ignore=shutil.ignore_patterns(".terraform"))
    target = work / file
    text = target.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not found in {file}"
    target.write_text(text.replace(old, new), encoding="utf-8")
    env = {**os.environ, "TF_DATA_DIR": str(INFRA / ".terraform")}     # reuse the initialised providers
    r = subprocess.run([TERRAFORM, "test", "-no-color"], cwd=work, env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode != 0, "terraform test should have failed"
    assert expected in r.stdout + r.stderr
