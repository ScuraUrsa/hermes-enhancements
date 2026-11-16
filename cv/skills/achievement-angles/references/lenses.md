# Lenses, company profiles and roles

## Lens catalogue

| Lens | Question to ask the facts | Vocabulary | Preferred metrics |
|---|---|---|---|
| `devops` — DevOps / infrastructure | What did it change in how software is built, deployed and run? | CI/CD, IaC, automation, pipelines, containers, Terraform, Ansible, Kubernetes | deploy time, frequency, manual steps removed, environments, lead time |
| `platform` — platform / developer experience | How did it make other engineers faster or more independent? | self-service, golden paths, templates, internal platform, onboarding | teams served, time to first deploy, tickets avoided |
| `sre` — reliability | What did it do for uptime, incidents and recovery? | SLO, monitoring, alerting, observability, on-call, DR, backup | availability %, MTTR, incidents, RPO/RTO |
| `security` — security | Which risk did it reduce, detect or remove? | hardening, least privilege, vulnerability, secrets, zero trust, threat, audit findings | findings closed, CVEs fixed, secrets removed, attack surface |
| `iam` — identity and access | Who or what got which access, and how is it controlled now? | IAM, RBAC, Entra ID / Azure AD, SSO, MFA, PAM, joiner-mover-leaver, access reviews, service identities | accounts/identities, roles cleaned up, review time, MFA coverage |
| `compliance` — governance / compliance | What does it prove to an auditor or regulator? | policy as code, ISO 27001, SOC 2, DORA, NIS2, GDPR, audit trail, controls | audits passed, controls automated, evidence time |
| `cloud` — cloud architecture | What design decision did it make and why? | architecture, landing zone, networking, HA, multi-region, Azure/AWS/GCP | services, regions, scale |
| `finops` — cost | What did it save or make predictable? | cost optimisation, rightsizing, reservations, tagging, chargeback | money/month, % saved |
| `data` — data / automation | What data or workflow did it automate or make available? | ETL, scripting, Python, APIs, integrations, reporting | hours saved, records, reports |
| `leadership` — leading people | Whom did Filip lead, teach or coordinate, and what came out of it? | led, mentored, coordinated, stakeholders, roadmap, hiring | team size, people trained, projects delivered |
| `business` — business impact | What did the business, customers or users get? | customers, revenue, time to market, users, SLA | users, revenue, time to market |

Add a lens when a real achievement needs one that is missing (e.g. `ai` for LLM/agent work); keep this table as
the single list.

## Company profile → lens weights (0–3)

| Profile | devops | platform | sre | security | iam | compliance | cloud | finops | data | leadership | business |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Bank / fintech / insurance | 2 | 1 | 2 | 3 | 3 | 3 | 2 | 1 | 1 | 1 | 1 |
| Startup / scale-up | 3 | 2 | 2 | 1 | 1 | 0 | 2 | 2 | 2 | 1 | 3 |
| Enterprise / corporate | 2 | 2 | 2 | 2 | 3 | 2 | 2 | 2 | 1 | 2 | 1 |
| Software house / consulting | 3 | 1 | 1 | 1 | 1 | 1 | 3 | 1 | 1 | 2 | 2 |
| SaaS / big tech | 2 | 3 | 3 | 2 | 1 | 1 | 2 | 1 | 2 | 1 | 2 |
| Public sector | 1 | 1 | 2 | 2 | 2 | 3 | 1 | 1 | 1 | 1 | 1 |
| Security vendor / MSSP | 1 | 1 | 1 | 3 | 2 | 2 | 1 | 0 | 1 | 1 | 1 |

## Role → lens weights (0–3)

| Role | devops | platform | sre | security | iam | compliance | cloud | finops | data | leadership | business |
|---|---|---|---|---|---|---|---|---|---|---|---|
| DevOps Engineer | 3 | 2 | 2 | 1 | 1 | 0 | 2 | 1 | 1 | 0 | 1 |
| Platform Engineer | 2 | 3 | 2 | 1 | 1 | 0 | 2 | 1 | 1 | 0 | 1 |
| SRE | 2 | 1 | 3 | 1 | 0 | 0 | 2 | 1 | 1 | 0 | 1 |
| Cloud Engineer / Architect | 2 | 1 | 2 | 2 | 2 | 1 | 3 | 2 | 0 | 1 | 1 |
| Security / DevSecOps Engineer | 2 | 0 | 1 | 3 | 2 | 2 | 1 | 0 | 0 | 0 | 0 |
| IAM Engineer / Identity Architect | 0 | 0 | 0 | 2 | 3 | 2 | 1 | 0 | 1 | 0 | 1 |
| Team Lead / Engineering Manager | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 3 | 2 |

Profiles or roles not listed: pick the nearest row and say which one you used.
