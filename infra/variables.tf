variable "region" {
  description = "AWS region."
  type        = string
  default     = "us-east-1"
}

variable "env" {
  description = "Environment name, used in resource names."
  type        = string
  default     = "dev"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,15}$", var.env))
    error_message = "env must be 2-16 lowercase letters, digits or hyphens."
  }
}

variable "azs" {
  description = "Two or more availability zones in the region."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]

  validation {
    condition     = length(var.azs) >= 2
    error_message = "EKS needs subnets in at least two availability zones."
  }
}

variable "vpc_cidr" {
  type    = string
  default = "10.40.0.0/16"
}

variable "kubernetes_version" {
  type    = string
  default = "1.34"
}

variable "admin_cidrs" {
  description = "CIDRs allowed to reach the public Kubernetes API endpoint (your office or VPN). Never 0.0.0.0/0."
  type        = list(string)

  validation {
    condition     = length(var.admin_cidrs) > 0 && !contains(var.admin_cidrs, "0.0.0.0/0")
    error_message = "admin_cidrs must list specific networks; 0.0.0.0/0 would expose the API endpoint to the internet."
  }
}

variable "node_instance_types" {
  type    = list(string)
  default = ["t3.large"]
}

variable "node_scaling" {
  type    = object({ min = number, desired = number, max = number })
  default = { min = 2, desired = 2, max = 4 }

  validation {
    condition     = var.node_scaling.min <= var.node_scaling.desired && var.node_scaling.desired <= var.node_scaling.max
    error_message = "node_scaling must satisfy min <= desired <= max."
  }
}

variable "app_namespace" {
  description = "Kubernetes namespace the agents run in. The IRSA role trusts only this namespace and service account."
  type        = string
  default     = "kestrel"
}

variable "app_service_account" {
  type    = string
  default = "kestrel-agents"
}

variable "artifact_retention_days" {
  description = "How long eval results and generated artefacts are kept in S3."
  type        = number
  default     = 90
}
