terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0, < 7.0"
    }
  }

  # Remote state, configured per environment at init time:
  #   terraform init -backend-config=env/dev.s3.tfbackend
  backend "s3" {}
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      project    = "kestrel-agents"
      managed-by = "terraform"
      env        = var.env
    }
  }
}
