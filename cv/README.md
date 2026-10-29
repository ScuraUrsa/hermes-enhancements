# cv — Hermes skills for writing CVs

Two skills (agentskills.io format, work in Hermes and Claude Code):

| Skill | What | Deployed to |
|---|---|---|
| [`skills/cv-writer`](skills/cv-writer/SKILL.md) | CV tailored to a job ad and company research; chooses the CV language from the ad or the research, translates and localizes it (conventions per market in [`references/localization.md`](skills/cv-writer/references/localization.md)); renders PDF with RenderCV | `~/.hermes/skills/productivity/cv-writer/` |
| [`skills/achievement-angles`](skills/achievement-angles/SKILL.md) | Writes the same achievement through different lenses (DevOps/infra, security, IAM, SRE, FinOps, leadership, …) and picks the one that fits the company profile and role; keeps the achievement bank | `~/.hermes/skills/productivity/achievement-angles/` |

State on prod: `~/.hermes/autonomy/cv/` (`master.yaml`, `achievements.yaml`, `applications/`), inside the
nightly backup. No secrets, no services, no cron.

Research behind the choice of tools: project file `cv/research-2026-10-20.md` in the Claude project.

## Install (prod)

```bash
# from a checkout of this repo, on the PC
scp -r cv/skills/cv-writer cv/skills/achievement-angles ubuntu@192.168.56.107:/tmp/
ssh ubuntu@192.168.56.107 '
  mkdir -p ~/.hermes/skills/productivity ~/.hermes/autonomy/cv/applications &&
  rm -rf ~/.hermes/skills/productivity/cv-writer ~/.hermes/skills/productivity/achievement-angles &&
  mv /tmp/cv-writer /tmp/achievement-angles ~/.hermes/skills/productivity/ &&
  python3 -m venv ~/.hermes/autonomy/cv/venv &&
  ~/.hermes/autonomy/cv/venv/bin/pip install -q "rendercv[full]" &&
  ~/.hermes/autonomy/cv/venv/bin/rendercv --version'
```

Optional, from the research: the official RenderCV skill (`hermes skills install rendercv/rendercv-skill/rendercv`)
for deeper knowledge of the YAML schema and themes.

## Notes

- RenderCV 2.8 has no built-in Polish locale; [`locale-pl.yaml`](skills/cv-writer/references/locale-pl.yaml)
  overrides every string (tested: "wrz 2018 – maj 2023", "cze 2023 – obecnie").
- Rendering downloads Typst packages from `packages.typst.org` on first use, so the VM needs internet then.
