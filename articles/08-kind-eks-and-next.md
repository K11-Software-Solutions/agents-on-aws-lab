# 08. kind in CI, Real EKS, and What Comes Next

*Agents on AWS Lab, article 8 of 8*

## A real cluster on every push

The `kind` job creates a Kubernetes cluster inside Docker on the CI runner and deploys for real:

1. check out **lab 7 at a pinned commit** (`d569c15`) and build its image, so this lab always tests
   a known version;
2. `kind load` the image, and `helm install --wait` with the kind values (fake provider, no AWS);
3. inside a real pod: uid 10001, `/app` not writable, `/tmp` writable;
4. port-forward to the **Service** and run **lab 7's eval gate**: the same gate, now through
   Kubernetes networking;
5. `helm upgrade --wait --rollback-on-failure` to a **shadow rollout**: a rolling update with no
   lost capacity, rolled back automatically if the new pods never become ready;
6. send 30 requests, collect the **pods' logs** with `kubectl logs`, and run **lab 7's promotion
   gate**, which must say *promote*.

That's the whole path from an image to a gated rollout, on infrastructure that costs nothing.

## Real EKS, when you choose

The `eks-plan` job runs only when you start it by hand. It uses **GitHub's OIDC token** to assume an
AWS role, so no AWS keys are stored in GitHub, and runs `terraform plan` against remote state. To
enable it, create an IAM role that trusts your repository's OIDC subject, then set the
`AWS_PLAN_ROLE_ARN` and `TF_STATE_BUCKET` repository variables.

Applying is deliberately left out of CI. Do it from a reviewed plan, in a sandbox account first,
and `terraform destroy` afterwards. The README lists what runs up a bill.

## What this lab didn't do

- `terraform apply` against a real account.
- The External Secrets Operator path.
- The AWS load balancer controller, an Ingress and TLS.
- Cluster autoscaling (Karpenter), and Bedrock as an alternative model provider (`bedrock:InvokeModel`
  on specific model ARNs, in the same IRSA pattern).

Each is a well-trodden next step, and each needs a real account to verify.

## Next: lab 9, operating agents

The service is deployed. Lab 9 covers running it: traces across model and tool calls, token and cost
metrics per route and variant, alerts on the signals lab 7's logs already emit, budgets that stop
runaway spend, scheduled agents, and what to do when the model provider has an incident.
