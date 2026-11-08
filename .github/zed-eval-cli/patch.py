"""Patches applied to Zed's crates/eval_cli before the build. Run from the Zed checkout root.

p1  The agent settings template ends with `}}"` inside the raw string, so every run fails with
    "Failed to migrate settings: trailing characters at line 14 column 18". Drop the stray quote.

p2  Terminal tool hang. Zed's agent wraps terminal commands in a bubblewrap sandbox on Linux
    (feature flag `sandboxing`, on for everyone) and re-executes the *current binary* inside it
    with `--zed-linux-sandbox-launcher ...`. Zed's own main() handles that flag
    (`sandbox::run_sandbox_launcher_if_invoked()`); eval-cli's main() does not, so clap rejects it
    and every command fails with "unexpected argument '--zed-linux-sandbox-launcher' found"
    (exit 2). The model then asks to run `unsandboxed`, or Zed offers a sandbox fallback (no bwrap,
    as on the prod VM), and both are UI permission prompts that nobody answers headless: the run
    waits until its timeout.
    Fix: (a) call the launcher hook first thing in main(), like Zed does, and (b) run terminal
    commands unsandboxed by default (`agent.sandbox_permissions.allow_unsandboxed`), so no
    escalation prompt can block a headless run. Set ZED_EVAL_SANDBOX=1 to keep the sandbox
    (needs bwrap; network/write escalations would still need a prompt that nobody answers).
"""

import re

MAIN = "crates/eval_cli/src/main.rs"
CARGO = "crates/eval_cli/Cargo.toml"


def sub1(pattern, repl, s, what):
    new, n = re.subn(pattern, repl, s)
    assert n == 1, f"patch target not found ({what}): {n}"
    return new


s = open(MAIN).read()

# p1: stray quote at the end of the settings template
s = sub1(r'("format_on_save": "off"\n[ ]*[}][}])"(\n[ ]*"#)', r"\1\2", s, "settings quote")

# p2a: handle the sandbox launcher re-exec before clap sees the arguments
s = sub1(
    r"fn main\(\) \{\n    let args = Args::parse\(\);",
    "fn main() {\n"
    "    // hermes p2: bwrap re-executes this binary with --zed-linux-sandbox-launcher to run\n"
    "    // sandboxed terminal commands; handle it before argument parsing, as Zed's main() does.\n"
    "    sandbox::run_sandbox_launcher_if_invoked();\n"
    "    let args = Args::parse();",
    s,
    "main hook",
)

# p2b: unsandboxed terminal by default (ZED_EVAL_SANDBOX=1 keeps the sandbox)
s = sub1(
    r'(\n( *)let settings = format!\(\n *r#"\{\{\n *"language_models": \{language_models_settings\},\n *"agent": \{\{\n)( *)("tool_permissions": \{\{"default": "allow"\}\},\n)',
    lambda m: (
        "\n" + m.group(2) + "// hermes p2: no sandbox escalation prompts in a headless run\n"
        + m.group(2) + 'let allow_unsandboxed = !std::env::var("ZED_EVAL_SANDBOX").is_ok_and(|v| v == "1");'
        + m.group(1)
        + m.group(3) + m.group(4)
        + m.group(3) + '"sandbox_permissions": {{"allow_unsandboxed": {allow_unsandboxed}}},\n'
    ),
    s,
    "sandbox settings",
)
open(MAIN, "w").write(s)

c = open(CARGO).read()
c = sub1(r"\nserde\.workspace = true\n", "\nsandbox.workspace = true\nserde.workspace = true\n", c, "cargo dep")
open(CARGO, "w").write(c)
print("eval-cli patched: p1 settings quote, p2 sandbox launcher + unsandboxed default")
