# 12 · Managed SaaS business (Nextcloud + Desktop-as-a-Service, managed CI/CD)

**Status vs Hermes:** new. There is only a `nextcloud-deployment` repo (in the runner list; CI failing 4/20). No business plan exists.
**Priority:** P5 (business exploration, not a Hermes feature)

## Goal and context
Filip explored selling managed services that run on Azure. The topics:
- whether reselling Azure is allowed, and the alternative of SaaS that manages a customer-owned Azure tenant
- becoming a Microsoft CSP
- distributing via Ingram Micro, and what code he'd need for that integration
- products: managed Nextcloud and Desktop-as-a-Service
- whether a managed CI/CD runner offering counts as SaaS

Source: fjkazmierczak account.
- *SaaS with Azure accounts* (2025-08-22)
- *Porównanie architektur runnerów* (2025-09-16, the SaaS question)

## Architecture
```
Customer tenant (customer owns subscription; Filip has delegated access via Azure Lighthouse)
   ├─ Nextcloud (AKS or VM scale set, Azure Files/Blob, Postgres flexible server)
   ├─ DaaS: Azure Virtual Desktop host pools from Packer images (see 01/02)
   └─ optional: self-hosted CI runners (image factory from 02)
Control plane (Filip's tenant): Terraform modules per product, provisioning pipeline,
   billing (Stripe) + marketplace listing / distributor (Ingram Micro Cloud Marketplace) later
```
Managing a customer-owned tenant (Lighthouse) avoids the reselling question. You sell the management, and the customer pays Microsoft directly. CSP or Ingram come only after there are paying customers.

## Implementation plan
1. Validate demand first: find 3 potential customers (small firms), interview them, and settle a price point.
2. Productise one offer (managed Nextcloud) as Terraform modules plus a runbook. Reuse `nextcloud-deployment` once its CI is fixed.
3. Lighthouse onboarding template (ARM/Bicep) and a monitoring baseline.
4. Write legal and pricing docs. Register in the Microsoft partner network. Look at CSP indirect resellers (Ingram/TD Synnex) only if volume justifies it.

## Deployment plan
A demo tenant on an Azure free or credit subscription. No production customers before a security review and a backup/restore drill.

## Configuration
Per-customer tfvars, Lighthouse offer definition, monitoring alerts.

## Cost / hardware
- Demo: roughly €50–150/month while running.
- Business overhead: accounting, insurance, MPN registration.

## Open questions
- Does this conflict with Filip's employment contract?
- Is this a serious business goal or just exploration? It is parked at P5 until Filip decides.
