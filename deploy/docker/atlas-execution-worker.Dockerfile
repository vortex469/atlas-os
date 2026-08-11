FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ARG CODEX_CLI_VERSION=0.147.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/opt/atlas/services/atlas-agent:/opt/atlas/services/atlas-execution-worker

WORKDIR /opt/atlas/services/atlas-execution-worker

COPY services/atlas-agent/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --requirement /tmp/requirements.txt \
    && apt-get update \
    && apt-get install --no-install-recommends --yes \
        bubblewrap \
        ca-certificates \
        git \
        npm \
    && npm install --global --omit=dev "@openai/codex@${CODEX_CLI_VERSION}" \
    && command -v codex \
    && codex --version \
    && command -v bwrap \
    && bwrap --version \
    && git --version \
    && rm -rf /var/lib/apt/lists/* /tmp/requirements.txt

COPY services/atlas-agent/app /opt/atlas/services/atlas-agent/app
COPY services/atlas-execution-worker/atlas_execution_worker ./atlas_execution_worker
COPY services/atlas-execution-worker/healthcheck.py ./healthcheck.py
COPY deploy/docker/atlas-execution-worker-entrypoint.sh /usr/local/bin/atlas-execution-worker-entrypoint

RUN groupadd --gid 10001 atlas \
    && useradd \
        --uid 10001 \
        --gid atlas \
        --home-dir /opt/atlas \
        --no-create-home \
        --shell /usr/sbin/nologin \
        atlas \
    && mkdir -p /run/atlas-execution-worker /run/secrets /opt/atlas/.codex /opt/atlas/execution-worker-state \
    && touch /run/secrets/codex-auth.json \
    && chmod 0444 /run/secrets/codex-auth.json \
    && chown -R atlas:atlas /run/atlas-execution-worker /opt/atlas

USER atlas

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "/opt/atlas/services/atlas-execution-worker/healthcheck.py"]

ENTRYPOINT ["/usr/local/bin/atlas-execution-worker-entrypoint"]
CMD ["python", "-m", "atlas_execution_worker.main"]
