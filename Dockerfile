ARG PYTHON_VERSION=3.12

# https://hub.docker.com/_/python
FROM python:"${PYTHON_VERSION}"-slim

ARG CODE_LOCATION

# set container envs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH=/app/.venv/bin:"${PATH}"

# set workdir
WORKDIR /app

# Install dependencies
RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --compile-bytecode --no-editable

# Copy the project into the image
COPY . /app

# Sync the project
RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --frozen --no-editable

# install dbt project
RUN dagster-dbt project prepare-and-package \
    --file src/teamster/code_locations/"${CODE_LOCATION}"/__init__.py