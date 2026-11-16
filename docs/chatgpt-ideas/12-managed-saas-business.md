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

Also from the **kazmierczakfilipjan** account:
- *Qubes OS Deployment Options* (2025-07-01, "Qubes OS as a service" on Proxmox/OpenStack vs containers)
- *Compute resource estimation methods* (2025-08-23, right-sizing a web app and Desktop-as-a-Service)
- *Naming Open Source Platform*, *Currency Naming Suggestions*, *Darmowe opcje deploymentu* (2026-02-11, a brand for an open-source AI + cloud platform with an internal credit currency; whether a SaaS on CrewAI/LangGraph may be sold)
- *Shared Subscription Legal Issues* (2026-02-17, a credential-pool service for streaming: rejected as illegal)
- *Amazon Oracle Custom OS* (2026-04-23, thin clients replacing PCs: build your own thin-client OS?)

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

## Additions from the kazmierczakfilipjan account
- **Thin-client DaaS.** Don't build an OS. Use a stock thin-client distro (e.g. IGEL-like Linux, or a locked-down Debian kiosk with the RDP/Moonlight client), and spend the effort on the VDI back end and sizing.
- **Sizing method.** Load-test one reference desktop/web profile (k6 for web, a scripted desktop workload for DaaS), find the knee point, then size at ~70 % of it. Re-measure on every major image change.
- **Platform credits.** One internal unit ("credits") priced against cost of tokens + compute is simpler than a branded currency. Branding (the FAVICUP idea) can come later.
- **Licensing.** CrewAI and LangChain/LangGraph core are MIT and fine for a commercial SaaS. LangSmith self-hosting is a paid enterprise product. Credential-pooling for streaming services is out: it breaks the services' terms and probably the law.
- **Qubes-as-a-service.** Not practical (Qubes needs bare metal and its own Xen). The sellable version is per-app isolated workspaces (containers or microVMs, see [27](27-agent-sandboxes.md)).

## Open questions
- Does this conflict with Filip's employment contract?
- Is this a serious business goal or just exploration? It is parked at P5 until Filip decides.
