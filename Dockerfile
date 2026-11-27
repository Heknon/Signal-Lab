# syntax=docker/dockerfile:1.7
# One image, three roles: the lab API (default), the code runner, and the
# shop scenario services. See compose.yaml and charts/signal-lab.

FROM oven/bun:1.4.4 AS web
WORKDIR /web
COPY web/package.json web/bun.lock ./
# Behind a TLS-intercepting proxy? Pass its CA: --secret id=ca_bundle,src=/path/ca.pem
RUN --mount=type=secret,id=ca_bundle,required=false \
    if [ -f /run/secrets/ca_bundle ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/ca_bundle; fi; \
    bun install --frozen-lockfile
COPY web/ ./
RUN bun run build

FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY server/requirements.txt server/requirements.txt
RUN --mount=type=secret,id=ca_bundle,required=false \
    if [ -f /run/secrets/ca_bundle ]; then export PIP_CERT=/run/secrets/ca_bundle; fi; \
    pip install -r server/requirements.txt
COPY server/ server/
COPY plugins/ plugins/
COPY deploy/ deploy/
COPY --from=web /web/dist web/dist
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin lab
USER 10001
ENV PYTHONPATH=/app/server \
    SIGNAL_LAB_PLUGINS_DIR=/app/plugins \
    SIGNAL_LAB_STATIC_DIR=/app/web/dist
EXPOSE 8000
ENTRYPOINT ["python", "-m", "signal_lab"]
CMD ["api"]
