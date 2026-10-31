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
# Zed: build eval-cli from the Zed repo (cargo build --release -p eval_cli) and
# copy the binary to docker/eval-cli and uncomment the COPY line below.
FROM python:3.12-slim-bookworm

ARG CLAUDE_CODE_VERSION=latest
ARG COPILOT_CLI_VERSION=latest

RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates ripgrep gh \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*
RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" "@github/copilot@${COPILOT_CLI_VERSION}"
RUN pip install --no-cache-dir uv
# COPY docker/eval-cli /usr/local/bin/eval-cli   # uncomment once the Zed binary is built

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
