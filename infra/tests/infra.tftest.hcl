# terraform test, with a mocked AWS provider: no account, no credentials, no cost.
# The mock fills in computed values (ids, ARNs); overrides below give the few that other
# resources parse a realistic shape.

mock_provider "aws" {
  override_resource {
    target = aws_eks_cluster.this
    values = {
      arn      = "arn:aws:eks:us-east-1:111122223333:cluster/kestrel-dev"
      identity = [{ oidc = [{ issuer = "https://oidc.eks.us-east-1.amazonaws.com/id/EXAMPLED539D4633E53DE1B71EXAMPLE" }] }]
    }
  }
  override_resource {
    target = aws_iam_openid_connect_provider.eks
    values = { arn = "arn:aws:iam::111122223333:oidc-provider/oidc.eks.us-east-1.amazonaws.com/id/EXAMPLED539D4633E53DE1B71EXAMPLE" }
  }
  override_resource {
    target = aws_kms_key.this
    values = { arn = "arn:aws:kms:us-east-1:111122223333:key/1234abcd-12ab-34cd-56ef-1234567890ab", key_id = "1234abcd-12ab-34cd-56ef-1234567890ab" }
  }
  override_resource {
    target = aws_s3_bucket.artifacts
    values = { arn = "arn:aws:s3:::kestrel-dev-artifacts-example", id = "kestrel-dev-artifacts-example", bucket = "kestrel-dev-artifacts-example" }
  }
  override_resource {
    target = aws_secretsmanager_secret.anthropic_api_key
    values = { arn = "arn:aws:secretsmanager:us-east-1:111122223333:secret:kestrel-dev/anthropic-api-key-abc123" }
  }
  override_resource {
    target = aws_iam_role.cluster
    values = { arn = "arn:aws:iam::111122223333:role/kestrel-dev-cluster" }
  }
  override_resource {
    target = aws_iam_role.node
    values = { arn = "arn:aws:iam::111122223333:role/kestrel-dev-node" }
  }
}

variables {
  admin_cidrs = ["203.0.113.0/24"]
}

run "network_keeps_nodes_private" {
  command = apply

  assert {
    condition     = length(aws_subnet.private) == 2 && length(aws_subnet.public) == 2
    error_message = "expected a public and a private subnet in each of two AZs"
  }
  assert {
    condition     = alltrue([for s in aws_subnet.public : s.map_public_ip_on_launch == false])
    error_message = "public subnets must not hand out public IPs"
  }
  assert {
    condition     = toset(aws_eks_node_group.default.subnet_ids) == toset([for s in aws_subnet.private : s.id])
    error_message = "nodes must run in the private subnets only"
  }
}

run "cluster_is_locked_down" {
  command = apply

  assert {
    condition     = aws_eks_cluster.this.vpc_config[0].public_access_cidrs == toset(["203.0.113.0/24"])
    error_message = "the public API endpoint must be limited to admin_cidrs"
  }
  assert {
    condition     = aws_eks_cluster.this.vpc_config[0].endpoint_private_access
    error_message = "the private API endpoint must be on"
  }
  assert {
    condition     = contains(aws_eks_cluster.this.encryption_config[0].resources, "secrets")
    error_message = "Kubernetes secrets must be encrypted with the KMS key"
  }
  assert {
    condition     = contains(aws_eks_cluster.this.enabled_cluster_log_types, "audit")
    error_message = "control-plane audit logs must be enabled"
  }
  assert {
    condition     = aws_eks_cluster.this.access_config[0].authentication_mode == "API"
    error_message = "use EKS access entries, not the aws-auth ConfigMap"
  }
}

run "irsa_trusts_one_service_account" {
  command = apply

  assert {
    condition = jsondecode(aws_iam_role.app.assume_role_policy).Statement[0].Condition.StringEquals[
      "oidc.eks.us-east-1.amazonaws.com/id/EXAMPLED539D4633E53DE1B71EXAMPLE:sub"
    ] == "system:serviceaccount:kestrel:kestrel-agents"
    error_message = "the app role must trust exactly the kestrel/kestrel-agents service account"
  }
  assert {
    condition = jsondecode(aws_iam_role.app.assume_role_policy).Statement[0].Condition.StringEquals[
      "oidc.eks.us-east-1.amazonaws.com/id/EXAMPLED539D4633E53DE1B71EXAMPLE:aud"
    ] == "sts.amazonaws.com"
    error_message = "the app role must check the token audience"
  }
}

run "app_policy_is_least_privilege" {
  command = apply

  assert {
    condition = alltrue(flatten([
      for s in jsondecode(aws_iam_role_policy.app.policy).Statement :
      [for a in flatten([s.Action]) : !strcontains(a, "*")]
    ]))
    error_message = "no wildcard actions in the app policy"
  }
  assert {
    condition = alltrue([
      for s in jsondecode(aws_iam_role_policy.app.policy).Statement :
      s.Resource != "*"
    ])
    error_message = "no wildcard resources in the app policy"
  }
  assert {
    condition = anytrue([
      for s in jsondecode(aws_iam_role_policy.app.policy).Statement :
      s.Resource == "arn:aws:s3:::kestrel-dev-artifacts-example/eval-results/*"
    ])
    error_message = "S3 writes must be limited to the eval-results/ prefix"
  }
}

run "storage_is_private_and_encrypted" {
  command = apply

  assert {
    condition = alltrue([
      aws_s3_bucket_public_access_block.artifacts.block_public_acls,
      aws_s3_bucket_public_access_block.artifacts.block_public_policy,
      aws_s3_bucket_public_access_block.artifacts.ignore_public_acls,
      aws_s3_bucket_public_access_block.artifacts.restrict_public_buckets,
    ])
    error_message = "all four S3 public-access blocks must be on"
  }
  assert {
    condition     = one(one(aws_s3_bucket_server_side_encryption_configuration.artifacts.rule).apply_server_side_encryption_by_default).sse_algorithm == "aws:kms"
    error_message = "artefacts must be encrypted with KMS"
  }
  assert {
    condition     = jsondecode(aws_s3_bucket_policy.artifacts.policy).Statement[0].Condition.Bool["aws:SecureTransport"] == "false"
    error_message = "the bucket must refuse non-TLS requests"
  }
  assert {
    condition     = aws_ecr_repository.agents.image_tag_mutability == "IMMUTABLE"
    error_message = "image tags must be immutable"
  }
  assert {
    condition     = aws_kms_key.this.enable_key_rotation
    error_message = "KMS key rotation must be on"
  }
}

# --- negative controls: inputs that must be rejected ------------------------------------------

run "rejects_an_open_api_endpoint" {
  command = plan
  variables {
    admin_cidrs = ["0.0.0.0/0"]
  }
  expect_failures = [var.admin_cidrs]
}

run "rejects_a_single_az" {
  command = plan
  variables {
    azs = ["us-east-1a"]
  }
  expect_failures = [var.azs]
}

run "rejects_impossible_scaling" {
  command = plan
  variables {
    node_scaling = { min = 3, desired = 2, max = 4 }
  }
  expect_failures = [var.node_scaling]
}
