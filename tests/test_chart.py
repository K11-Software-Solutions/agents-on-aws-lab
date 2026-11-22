"""The Helm chart, checked on what it renders. Needs helm on PATH (or HELM=/path/to/helm)."""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "charts" / "kestrel-agents"
HELM = os.environ.get("HELM") or shutil.which("helm")
pytestmark = pytest.mark.skipif(not HELM, reason="helm not installed")


def render(*args: str) -> dict:
    out = subprocess.run([HELM, "template", "t", str(CHART), *args], capture_output=True, text=True, check=True).stdout
    return {f"{d['kind']}/{d['metadata']['name']}": d for d in yaml.safe_load_all(out) if d}


def render_error(*args: str) -> str:
    r = subprocess.run([HELM, "template", "t", str(CHART), *args], capture_output=True, text=True)
    assert r.returncode != 0, "expected helm template to fail"
    return r.stderr


def container(m: dict) -> dict:
    return m["Deployment/t"]["spec"]["template"]["spec"]["containers"][0]


EKS = ["-f", str(ROOT / "charts" / "values" / "eks.yaml")]


def test_lint_strict():
    for args in ([], EKS):
        subprocess.run([HELM, "lint", str(CHART), "--strict", *args], check=True, capture_output=True)


def test_default_render_has_every_part():
    assert set(render()) == {"ServiceAccount/kestrel-agents", "ConfigMap/t", "Service/t", "Deployment/t",
                             "HorizontalPodAutoscaler/t", "PodDisruptionBudget/t", "NetworkPolicy/t"}


def test_pod_is_hardened():
    m = render()
    pod = m["Deployment/t"]["spec"]["template"]["spec"]
    c = container(m)
    assert pod["securityContext"]["runAsNonRoot"] is True and pod["securityContext"]["runAsUser"] == 10001
    assert pod["securityContext"]["seccompProfile"]["type"] == "RuntimeDefault"
    assert c["securityContext"] == {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]}}
    assert c["resources"]["limits"]["memory"] and c["resources"]["requests"]["cpu"]
    assert {"name": "tmp", "mountPath": "/tmp"} in c["volumeMounts"]          # read-only root, writable /tmp


def test_probes_use_lab7_endpoints():
    c = container(render())
    assert c["livenessProbe"]["httpGet"]["path"] == "/healthz"
    assert c["readinessProbe"]["httpGet"]["path"] == "/readyz"
    assert c["startupProbe"]["httpGet"]["path"] == "/healthz"


def test_rolling_update_never_drops_capacity():
    strategy = render()["Deployment/t"]["spec"]["strategy"]
    assert strategy["rollingUpdate"]["maxUnavailable"] == 0


def test_without_aws_the_pod_gets_no_credentials():
    m = render()
    assert "annotations" not in m["ServiceAccount/kestrel-agents"]["metadata"]
    assert m["Deployment/t"]["spec"]["template"]["spec"]["automountServiceAccountToken"] is False


def test_on_eks_the_pod_uses_irsa_and_secrets_manager():
    m = render(*EKS)
    sa = m["ServiceAccount/kestrel-agents"]["metadata"]
    assert sa["annotations"]["eks.amazonaws.com/role-arn"].startswith("arn:aws:iam::")
    assert m["Deployment/t"]["spec"]["template"]["spec"]["automountServiceAccountToken"] is True
    env = container(m)["env"]
    assert env == [{"name": "ANTHROPIC_API_KEY", "valueFrom": {"secretKeyRef": {"name": "kestrel-anthropic-api-key", "key": "ANTHROPIC_API_KEY"}}}]
    es = m["ExternalSecret/kestrel-anthropic-api-key"]["spec"]
    assert es["data"][0]["remoteRef"]["key"].startswith("arn:aws:secretsmanager:")


def test_no_secret_values_are_ever_rendered():
    for args in ([], EKS):
        docs = render(*args)
        assert not any(k.startswith("Secret/") for k in docs)
        assert "ANTHROPIC_API_KEY" not in str(docs["ConfigMap/t"]["data"])


def test_rollout_values_become_environment():
    data = render("--set", "rollout.candidate.effort=low", "--set", "rollout.shadowPercent=25")["ConfigMap/t"]["data"]
    assert data["CANDIDATE_EFFORT"] == "low" and data["SHADOW_PERCENT"] == "25"


def test_config_change_restarts_pods():
    a = render()["Deployment/t"]["spec"]["template"]["metadata"]["annotations"]["checksum/config"]
    b = render("--set", "model.effort=high")["Deployment/t"]["spec"]["template"]["metadata"]["annotations"]["checksum/config"]
    assert a != b


def test_network_policy_allows_only_dns_and_https_out():
    egress = render()["NetworkPolicy/t"]["spec"]["egress"]
    ports = sorted((p["port"], p["protocol"]) for rule in egress for p in rule["ports"])
    assert ports == [(53, "TCP"), (53, "UDP"), (443, "TCP")]


@pytest.mark.parametrize("args, message", [
    (["--set", "rollout.shadowPercent=10"], "rollout.candidate is empty"),
    (["--set", "rollout.candidate.effort=low", "--set", "rollout.shadowPercent=10", "--set", "rollout.candidatePercent=10"], "not both"),
    (["--set", "model.provider=claude", "--set", "model.apiKeySecret.name="], "needs model.apiKeySecret.name"),
    (["--set", "externalSecret.enabled=true"], "remoteKey is required"),
])
def test_unsafe_values_are_refused(args, message):
    assert message in render_error(*args)


def test_service_account_matches_the_irsa_trust_policy():
    """The chart and the Terraform must agree, or IRSA silently fails at run time."""
    tf = (ROOT / "infra" / "variables.tf").read_text(encoding="utf-8")
    ns = re.search(r'variable "app_namespace".*?default\s*=\s*"([^"]+)"', tf, re.S).group(1)
    sa = re.search(r'variable "app_service_account".*?default\s*=\s*"([^"]+)"', tf, re.S).group(1)
    assert render()["ServiceAccount/kestrel-agents"]["metadata"]["name"] == sa
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert f"--namespace {ns}" in workflow
