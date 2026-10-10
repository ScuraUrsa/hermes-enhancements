# Zed eval-cli (prebuilt)

Static x86_64 Linux (musl) build of Zed's headless agent runner, `crates/eval_cli`, from
zed-industries/zed commit f16f9652ec57bf806e65b2a0d51bb92a63644914 (GPL-3.0, source at that commit).
Built with `cargo zigbuild --release --package eval_cli --target x86_64-unknown-linux-musl`.

    xz -d eval-cli.xz && chmod +x eval-cli
    sha256 eval-cli     addd4b24c2012d1653f67858cfb6e86f2931a336e6105f98172747ddda117850
    sha256 eval-cli.xz  b187c2a3f4935504be1677b48e25003ebffc1ca0f0aac94cd89be10104b46fda

Used by hbench's `zed` agent (bench/hbench/agents/zed.py on the main branches).
