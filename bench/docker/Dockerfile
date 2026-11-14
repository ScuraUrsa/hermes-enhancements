# Sandbox image for hbench runs: agents run with permissions bypassed, so they
# get a throwaway container, a non-root user and only the keys for one provider.
#
#   docker build -t hbench -f docker/Dockerfile .
#   docker run --rm -it --env-file ~/.hbench.env \
#     -v "$PWD/results:/bench/results" -v /home/ubuntu:/repos:ro \
#     -v /home/ubuntu/.hermes/hermes-agent:/repos2/hermes-agent:ro -e HBENCH_REPOS=/repos:/repos2 \
#     --add-host=host.docker.internal:host-gateway hbench matrix matrix.toml
#
# On the dev VM hermes-agent lives in ~/.hermes, hence the second mount. gh is installed because
# crewai-orchestrator's tests shell out to it (unauthenticated it fails, like a pending CI check).
#
# Zed: eval-cli comes from release zed-eval-cli-f16f965-p1 of ScuraUrsa/hermes-enhancements
# (built from Zed source, settings-JSON fix), sha256-checked.
FROM python:3.15-slim-bookworm

ARG CLAUDE_CODE_VERSION=latest
ARG COPILOT_CLI_VERSION=latest
ARG EVAL_CLI_URL=https://github.com/ScuraUrsa/hermes-enhancements/releases/download/zed-eval-cli-f16f965-p1/eval-cli.xz
ARG EVAL_CLI_SHA256=6ee2acf8f9b354b13433c68401926fd75b24e12150be1b320839e4aeef9d5ac8

RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates ripgrep gh xz-utils \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*
RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" "@github/copilot@${COPILOT_CLI_VERSION}"
RUN pip install --no-cache-dir uv
RUN curl -fsSL "$EVAL_CLI_URL" | xz -d > /usr/local/bin/eval-cli \
    && echo "$EVAL_CLI_SHA256  /usr/local/bin/eval-cli" | sha256sum -c - \
    && chmod 755 /usr/local/bin/eval-cli

RUN useradd -m bench
WORKDIR /bench
COPY --chown=bench pyproject.toml providers.toml ./
COPY --chown=bench hbench ./hbench
COPY --chown=bench tasks ./tasks
COPY --chown=bench matrix.example.toml ./
RUN pip install --no-cache-dir -e .
USER bench
RUN git config --global --add safe.directory '*'
ENTRYPOINT ["hbench"]
