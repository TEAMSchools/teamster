# trunk-ignore-all(checkov/CKV_DOCKER_2)
# trunk-ignore-all(trivy/DS026)
# https://hub.docker.com/_/python
FROM python:3.13-slim
ARG CODE_LOCATION

# set container envs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:${PATH}"
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1

# install system deps & create non-root user
# trunk-ignore(hadolint/DL3008)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        openssh-client sshpass \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 1234 teamster \
    && useradd -m -u 1234 -g teamster teamster

# set workdir
WORKDIR /app

# install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

# copy & install python deps
COPY --chown=1234:1234 uv.lock pyproject.toml /app/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --no-editable

# copy & install dagster project
COPY --chown=1234:1234 src/teamster/ /app/src/teamster/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# copy & install dbt project
COPY --chown=1234:1234 "src/dbt/${CODE_LOCATION}/" "/app/src/dbt/${CODE_LOCATION}/"
RUN --mount=type=cache,target=/root/.cache/uv \
    dagster-dbt project prepare-and-package \
        --file "src/teamster/code_locations/${CODE_LOCATION}/__init__.py"

# Switch to the non-root user
USER 1234:1234