# https://hub.docker.com/_/python
FROM python:3.12-slim
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

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/
COPY uv.lock pyproject.toml /app/

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --no-editable

# Copy the project into the image
COPY src/ /app/src/

# Sync the project & install dbt project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable \
    && dagster-dbt project prepare-and-package \
        --file "src/teamster/code_locations/${CODE_LOCATION}/__init__.py"

# update non-root user permissions
RUN chown -R 1234:1234 /app

# Switch to the non-root user
USER 1234:1234