FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/opt/atlas/services/atlas-agent:/opt/atlas/services/atlas-execution-worker

WORKDIR /opt/atlas/services/atlas-execution-worker

COPY services/atlas-agent/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --requirement /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

COPY services/atlas-agent/app /opt/atlas/services/atlas-agent/app
COPY services/atlas-execution-worker/atlas_execution_worker ./atlas_execution_worker
COPY services/atlas-execution-worker/healthcheck.py ./healthcheck.py

RUN groupadd --gid 10001 atlas \
    && useradd \
        --uid 10001 \
        --gid atlas \
        --home-dir /opt/atlas \
        --no-create-home \
        --shell /usr/sbin/nologin \
        atlas \
    && mkdir -p /run/atlas-execution-worker /opt/atlas/.codex \
    && chown -R atlas:atlas /run/atlas-execution-worker /opt/atlas

USER atlas

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "/opt/atlas/services/atlas-execution-worker/healthcheck.py"]

ENTRYPOINT ["python", "-m", "atlas_execution_worker.main"]
