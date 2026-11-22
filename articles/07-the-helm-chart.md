# 07. The Helm Chart

*Agents on AWS Lab, article 7 of 8*

`charts/kestrel-agents` runs lab 7's image. It's tested on what it renders, not on how the
templates look.

## Probes from lab 7's endpoints

| Probe | Path | Effect when it fails |
|---|---|---|
| startup | `/healthz` | the other probes wait (up to 60 s) for start-up |
| liveness | `/healthz` | the container is restarted |
| readiness | `/readyz` | the pod is taken out of the Service, not restarted |

With `PROVIDER=claude` and no key, `/readyz` returns 503. The pod stays up and explains itself, but
gets no traffic.

## Hardening, matching the image

The pod runs with `runAsNonRoot`, uid 10001 (the image's user), `seccompProfile: RuntimeDefault`,
`readOnlyRootFilesystem`, all capabilities dropped and no privilege escalation, plus memory limits.
A writable `emptyDir` is mounted at `/tmp`. CI checks it in a real pod: `id -u` is 10001, writing
to `/app` fails, and writing to `/tmp` works.

## Availability

- **HPA** on CPU, 2 to 6 replicas.
- **PodDisruptionBudget** with `minAvailable: 1`, so node upgrades never take every pod at once.
- **Rolling updates** with `maxUnavailable: 0`: new pods must be ready before old ones go.
- **Topology spread** across zones.
- **A config checksum annotation**: changing a value restarts the pods. Without it, a ConfigMap
  change would wait for the next unrelated deploy.

## NetworkPolicy

Ingress is allowed only to port 8080. Egress is allowed only to DNS and HTTPS, which covers the
model API and AWS endpoints. A compromised pod can't scan the cluster. It's disabled on kind,
whose default CNI doesn't enforce policies; on EKS, enable network policy support in the VPC CNI.

## Values that can't go wrong silently

Lab 7 rejects bad rollout configuration at start-up. The chart rejects it earlier, at render time:

| Values | Error |
|---|---|
| a shadow percentage with no candidate | "rollout.candidate is empty" |
| shadow and canary together | "not both" |
| `provider: claude` with no secret name | "needs model.apiKeySecret.name" |
| `externalSecret.enabled` with no remote key | "remoteKey is required" |

Each has a test. `helm lint --strict` runs with the default values and the EKS example.
