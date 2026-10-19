# 18 · Kubernetes security learning path (CKS) + hardened private EKS reference

**Status vs Hermes:** new. The K8s POC series on kind clusters ended 2026-10-06. terraforge has a 2025 `aks_private` branch (AKS, not EKS). There is no CKS, EKS or interview-prep material.
**Priority:** P3

## Goal and context
Many 2025 work chats were about private EKS and AKS with Terraform:
- VPC endpoints and their availability zones
- the EKS security setup and the KMS module
- splitting state into several files with `terraform_remote_state`
- scanning modules with checkov
- liveness-probe and kubectl issues

Filip asked for code for a fully private EKS with no internet access, to research how to pass the **CKS** exam, and for prompts and cheat sheets to refresh Helm, Kustomize, AWS and EKS before a job interview. He also asked for help with a fresh CV. Taken together, these make a learning goal with a reusable reference repo as its output.

Source: fjkazmierczak account.
- *Private EKS with Terraform* (2025-03-17)
- *Get EKS Module Code* (2025-04-03)
- *Multiple state files in Terraform* (2025-04-03)
- *Terraform KMS module reuse* (2025-04-09)
- *VPC Endpoint AZ Błąd* (2025-05-20)
- *Terraform EKS Security Setup* (2025-05-21)
- *Separate State File Module* (2025-05-21)
- *Interview prep prompts LLM* (2025-08-21)
- *Create fresh CV* (2025-08-26)
- *K8s liveness probe 404* (2025-09-03)
- *Terraform conditional import block* (2026-10-01)

## Architecture
```
repo k8s-security-lab (private)
  ├─ terraform/eks-private/   VPC (no IGW/NAT), interface+gateway endpoints per AZ, EKS private endpoint,
  │                           KMS envelope encryption, IRSA/Pod Identity, separate states (network/cluster/addons)
  ├─ kind/cks-lab/            local CKS practice: PSA, NetworkPolicy, Falco, AppArmor/seccomp, audit logs,
  │                           kube-bench, trivy, OPA Gatekeeper/Kyverno, etcd encryption
  ├─ drills/                  timed exercises (killer.sh-style), one md per CKS domain
  └─ ci: checkov + tflint + trivy config on every PR
```
Hermes role: a skill `cks-coach` that picks a daily drill, checks the result on the kind cluster (scripted verification), and schedules spaced repetition via timeplane.

## Implementation plan
1. Write the CKS syllabus map (cluster setup, hardening, system hardening, microservice vulnerabilities, supply chain, runtime security) with a drill list.
2. A kind-based lab on the dev VM, created on demand and deleted afterwards (the cleanup lesson from 2026-10-06). Run one domain per week.
3. EKS reference: write it in Terraform, but only `plan` it in CI. Apply in a sandbox AWS account for under 2 hours, then destroy.
4. Interview kit: Helm/Kustomize/EKS cheat sheets and an LLM mock-interview prompt. Store as markdown, not a service.

## Deployment plan
The lab runs on demand only. The AWS sandbox has a budget alarm (€10) and a destroy job in CI.

## Configuration
AWS sandbox profile (credentials in Bitwarden), cluster version pinned to the current exam version.

## Cost / hardware
- The CKS exam costs about $445 (it requires an active CKA).
- An EKS test run is about $0.10/h for the control plane plus endpoints (~$0.01/h each per AZ), so keep it short.
- A kind cluster takes about 2–3 GB RAM. The prod VM has 8 GB, so use the dev VM.

## Open questions
- Does Filip hold an active CKA (a CKS prerequisite)?
- Is the goal certification, a job change, or just skill-up?
