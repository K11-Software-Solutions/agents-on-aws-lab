# 02. The Network

*Agents on AWS Lab, article 2 of 8*

`infra/network.tf` builds a VPC across two availability zones, with two kinds of subnet:

| Subnet | Holds | Route to the internet |
|---|---|---|
| public | NAT gateway, load balancers | internet gateway |
| private | EKS nodes and pods | NAT gateway (outbound only) |

Nodes have no public IP addresses, so nothing on the internet can connect to them directly. They
can still reach out, to the Claude API and image registries, through NAT.

## Details that matter

- **Subnet tags.** `kubernetes.io/role/elb` and `kubernetes.io/role/internal-elb` tell the AWS load
  balancer controller where to put public and internal load balancers.
- **`map_public_ip_on_launch = false`** even on public subnets. Nothing launched there should get a
  public IP by accident. A test checks it, and a negative control flips it to prove the test fails.
- **Two AZs minimum.** EKS requires subnets in at least two zones; a variable validation rejects a
  single zone before anything is planned.
- **One NAT gateway** keeps a dev environment cheap. If its zone fails, private subnets lose
  outbound access. For production, use one per zone.

## Subnets from one CIDR

```hcl
public  = { for i, az in var.azs : az => cidrsubnet(var.vpc_cidr, 8, i) }
private = { for i, az in var.azs : az => cidrsubnet(var.vpc_cidr, 8, i + 10) }
```

The ranges are computed, not hand-typed, so adding a third zone is a one-line variable change.
