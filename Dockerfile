FROM python:3.15-slim

WORKDIR /app

# Non-root user
RUN groupadd -r lerebel103 && useradd -r -g lerebel103 lerebel103

# uv for dependency management
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /usr/local/bin/uv

# Dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Production dependencies only (no dev group, no local project install)
RUN uv sync --no-dev --frozen --no-install-project

COPY app/ ./app/

# Version injected from the build arg (set by the Makefile and CI from the git tag)
ARG VERSION=dev
RUN printf '"""Version of the Fairland RS485 HA controller."""\n\n__version__ = "%s"\n' "${VERSION}" > app/version.py

RUN mkdir -p /etc/fairland-rs485-ha-controller && \
    chown -R lerebel103:lerebel103 /app /etc/fairland-rs485-ha-controller

USER lerebel103

ENV PYTHONPATH=/app

CMD [".venv/bin/python", "-m", "app", "--config", "/etc/fairland-rs485-ha-controller/config.yaml"]

LABEL maintainer="lerebel103"
LABEL description="Fairland RS485 HA controller - local Modbus TCP to MQTT bridge for Home Assistant"
LABEL version="${VERSION}"
