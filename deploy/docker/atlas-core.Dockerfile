FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /opt/atlas/services/atlas-core

COPY services/atlas-core/requirements.txt ./requirements.txt
RUN python -m pip install \
    --no-cache-dir \
    --requirement requirements.txt

COPY services/atlas-core/app ./app

RUN groupadd --gid 10001 atlas \
    && useradd \
        --uid 10001 \
        --gid atlas \
        --home-dir /opt/atlas \
        --no-create-home \
        --shell /usr/sbin/nologin \
        atlas \
    && mkdir -p \
        /opt/atlas/config \
        /opt/atlas/inventory \
        /opt/atlas/data \
    && chown atlas:atlas /opt/atlas/data

USER atlas

EXPOSE 8643

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8643/api/v1', timeout=3)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8643", "--no-access-log"]
