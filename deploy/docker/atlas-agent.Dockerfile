FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

ARG CODEX_CLI_VERSION=0.147.0

WORKDIR /opt/atlas/services/atlas-agent

RUN apt-get update \
    && apt-get install --no-install-recommends --yes \
        ca-certificates \
        git \
        npm \
    && rm -rf /var/lib/apt/lists/*

COPY services/atlas-agent/requirements.txt ./requirements.txt
RUN python -m pip install \
    --no-cache-dir \
    --requirement requirements.txt

RUN npm install --global --omit=dev @openai/codex@${CODEX_CLI_VERSION} \
    && command -v codex \
    && codex --version

COPY services/atlas-agent/app ./app
COPY deploy/docker/atlas-agent-entrypoint.sh /usr/local/bin/atlas-agent-entrypoint
RUN chmod 0755 /usr/local/bin/atlas-agent-entrypoint

RUN groupadd --gid 10001 atlas \
    && useradd \
        --uid 10001 \
        --gid atlas \
        --home-dir /opt/atlas \
        --no-create-home \
        --shell /usr/sbin/nologin \
        atlas \
    && mkdir -p \
        /opt/atlas/agent-state \
        /workspace/repository \
    && chown -R atlas:atlas \
        /opt/atlas/agent-state \
        /workspace

USER atlas

ENTRYPOINT ["/usr/local/bin/atlas-agent-entrypoint"]

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/health', timeout=3)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090", "--no-access-log"]
