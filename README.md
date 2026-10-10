# Zed eval-cli (prebuilt)

Static x86_64 Linux (musl) build of Zed's headless agent runner, `crates/eval_cli`, from
zed-industries/zed commit f16f9652ec57bf806e65b2a0d51bb92a63644914 (GPL-3.0, source at that commit)
plus `eval-cli-settings-fix.patch`.

The patch removes a stray `"` after the closing brace of the agent settings that `run_agent` writes. Without
it every run fails before the model is called with
`updating agent settings: Failed to migrate settings: trailing characters at line 14 column 18`
(still present on Zed main as of 2026-10-10).

Built with `git apply eval-cli-settings-fix.patch` and
`cargo zigbuild --release --package eval_cli --target x86_64-unknown-linux-musl`.

    xz -d eval-cli.xz && chmod +x eval-cli
    sha256 eval-cli     e2659e678128798b0b26959930e52b98d2754a17996ab479546a7c827bb23a45
    sha256 eval-cli.xz  1fa97352ee9a9946842f3fbc9f35c2a1a3276831618c7a6a9ca0addcd8b91a1a

Used by hbench's `zed` agent (bench/hbench/agents/zed.py) and installed on the Hermes VMs as
`~/.local/bin/zed-eval-cli` by WOBI's `coding_agents` role, which pins the sha256 above.
