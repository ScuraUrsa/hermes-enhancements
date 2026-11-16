# 02 · Self-hosted CI runner image factory

**Status vs Hermes:** partly exists. WOBI `iac/final` `ansible/roles/github_runner` already provides a runner per repo, an `ubuntu-latest`-like package set, a per-runner tool cache and cleanup hooks. `roles/base` has sha256-checked downloads. Not present: a manifest-driven multi-version toolcache (Ruby etc.) and a working Packer image pipeline (`packer-images` CI fails 13 of 16 runs).
**Priority:** P3

## Goal and context
Across many work-related chats, Filip designed an Azure Pipelines + Packer + Ansible factory for Ubuntu runner images. Its pieces:
- a central `config.yaml` that declares each tool and its install `type`
- downloads verified by checksum
- several Ruby versions installed the way GitHub's toolcache does it
- Azure tags passed into Packer as JSON
- reusable Packer file layouts

He also compared three runner architectures:
1. a full baked VM image
2. a small VM plus a shared, pre-populated disk
3. a minimal OS plus persistent tool containers or volumes

He asked whether managed CI/CD would count as SaaS.

Source: fjkazmierczak account.
- *Add tags to Packer* (2025-08-07)
- *Azure image definitions comparison* (2025-08-08)
- *Packer file structure reuse* (2025-08-13)
- *Provisioner overwrite check* (2025-08-13)
- *Install multiple Ruby versions* (2025-09-15)
- *Ruby package differences* (2025-09-15)
- *Porównanie architektur runnerów* (2025-09-16)
- *Merging vars in Ansible* (2025-09-17)
- *GitHub releases and assets* (2025-09-18)
- *Obtain file checksum* (2025-09-19)
- *Checksum filename explanation* (2025-09-22)
- *Ansible read HCL config* (2025-10-01)

Also from the **kazmierczakfilipjan** account (work CI threads, 2025-11 to 2026-07):
- *Scaling Azure DevOps Agents* (2026-03-16), *Skalowanie agentów na VM* (2026-02-20): several agent instances on one VM
- *Packer Reusable Templates* (2026-04-01): shared upload/provision blocks across builds
- *Storing Private Images on GHCR* (2026-04-09)
- *Ansible playbook compilation* and *Install Ansible offline* (2025-11-05): ship Ansible as a self-contained bundle to air-gapped VMs
- *CI/CD Tools Comparison* (2026-07-07): Azure DevOps / GitHub Actions vs Jenkins, and when to move to Forgejo Actions

## Architecture
```
tools.yaml (name, type: apt|binary|github_release|pipx|toolcache, versions[], checksum_url)
   │
   ├── Ansible role "toolset" (one task file per type, a shared verify-checksum helper)
   │      └── toolcache type → /opt/hostedtoolcache/<Tool>/<ver>/x64 + .complete marker
   │                            (compatible with setup-ruby / setup-python "use preinstalled")
   ├── Packer build → runner image (VirtualBox OVA locally; azure-arm optional)
   └── same role applied in place by WOBI github_runner (no image needed for 1-VM homelab)
```
Hybrid choice for Hermes: runners are long-lived on one VM, so architecture **#2/#3** fits best. Keep a persistent tool cache on disk, keep the runner work dirs ephemeral, and add a nightly cleanup. Baked images (#1) only pay off at scale.

## Implementation plan
1. Extract the tool list from `roles/github_runner` into `tools.yaml` and add the `toolcache` type. Ruby versions are built by `ruby-build`, or downloaded from `ruby/ruby-builder` releases with checksum verification.
2. Make the checksum helper generic: given a file URL and a checksum URL, parse the right line by file name, then use `get_url checksum:`.
3. Add molecule or `ansible-playbook --check` tests in CI, and a smoke test that runs `ruby -v` for each version.
4. Fix or retire the `packer-images` CI. It needs a VirtualBox-capable runner, which a GitHub-hosted runner cannot provide; use the Windows PC or skip the Packer step.

## Deployment plan
Change WOBI `iac/final` through a PR. Apply on the dev VM first (`pull.sh --role dev`), then prod. Runner downtime is limited to the restart of each runner service.

## Configuration
`group_vars/all/toolset.yml` (or `tools.yaml`), the runner labels (`self-hosted,linux,ruby`) and the cache path.

## Cost / hardware
Free on the existing VM. Watch disk use: each Ruby or Python version is about 100–300 MB, and the VM disk was at 51% after the 2026-10-06 cleanup.

## Additions from the kazmierczakfilipjan account
- **N agents per VM.** The runner role should take `runner_count` and create `agent-1..N` services with separate work dirs, so one large VM can run several jobs in parallel. This is cheaper than N small VMs for short jobs.
- **Reusable Packer parts.** Packer has no include mechanism. Use one `sources.pkr.hcl` plus shared `provisioner` script dirs, selected with `-only=` and variables, rather than copying templates.
- **Offline Ansible bundle.** Build a venv tarball (or a container image on GHCR) with ansible-core and the needed collections, so air-gapped hosts need only SSH and Python.
- **Forge choice.** Stay on GitHub plus self-hosted runners. Move to Forgejo Actions only if private-repo minutes or data-residency rules start to cost more than running a forge (backups, upgrades, SSO) yourself.

## Open questions
- Are any Hermes repos really going to need multi-version Ruby? If not, keep this only as a pattern.
- Is the Azure Pipelines and Azure Compute Gallery part a work topic only (not for Hermes)?

## Notes
The "managed CI/CD as SaaS" business angle is in [12-managed-saas-business.md](12-managed-saas-business.md).
