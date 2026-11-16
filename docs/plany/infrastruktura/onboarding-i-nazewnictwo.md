# Onboarding nowej maszyny i nazewnictwo (wskaźnik, 2026-10-22)

Obowiązujące nazewnictwo i szkic onboardingu są w repo **ScuraUrsa/hermes-workspace**, gałąź
`claude/project-thread-5906j7`, folder [`infra/`](https://github.com/ScuraUrsa/hermes-workspace/tree/claude/project-thread-5906j7/infra)
(`naming.md`, onboarding, hosty z pojemnością, stan monitoringu, backupy). Tam jest jedno źródło prawdy, ten plik
tylko do niego prowadzi i zbiera ustalenia z wątku o workerze.

Wcześniejsza wersja tego pliku proponowała nazwy `n01` / `lab-n01` i Proxmoxa. Jest wycofana, żeby nie było dwóch
konwencji: worker `lab-ubuntu` dostaje nazwę **`lab-w01`**, a VM-ki nazwy z `infra/naming.md`
(np. `k3s-dev-1`, `hermes-dev-1`).

## Ustalenia z wątku o workerze, do uwzględnienia w `infra/`

- Przed formatowaniem dysków: spis plików i kopia borg na Storage Box (`/borg/<nazwa>`), sprawdzenie logu kopii
  pod kątem błędów odczytu.
- Sieć kablowa bez DHCP (publiczne /29): `linux/net-static.sh` z zestawu USB. Adresy: .89 brama, .90 i .92 obce
  urządzenia, .91 laptop, .93 lab-w01, .94 ostatni wolny. VM-ki nie dostają adresów z tej puli: NAT + Tailscale.
- Bootstrap z pendrive'a (WOBI `bootstrap-usb`, gałąź `claude/project-thread-dzmkdd`): Tailscale, konto `hermes`,
  SSH, RustDesk, zapora tylko dla tailnetu, WoL. Potem z prod `ssh hermes@lab-…` i `collect-nodes.py`.

## Kiedy pierwsza VM na lab-w01 (runnery CI i inne)

1. Zadanie Filipa [T171](https://app.notion.com/p/lab-ubuntu-SSD-Cat6-cable-cooling-BIOS-and-Ubuntu-install-3ffee453d19e81a9a71feb2901bb0a38):
   SSD, Ubuntu Server, kabel Cat6, czyszczenie chłodzenia, BIOS. Termin 25.10.
2. Potem ok. 1–2 h. **Decyzja Filipa (22.10): k3s bezpośrednio na hoście lab-w01, bez VM w KVM.** GTX 1070 w klastrze
   bez passthrough, runnery CI jako pody (Actions Runner Controller), plan K12 sekcja 6.3. Realnie **26–27.10**.
3. Limity: jedna VM do 6 GB RAM i 4 vCPU (z 12 GB / 8 wątków), dysk na SSD, bez publicznego IP
   (NAT + Tailscale w VM). CPU bez AVX, łącze 100 Mb/s do wymiany kabla.

Wcześniej się nie da: system live znika przy każdym restarcie.
