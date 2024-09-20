# https://hub.docker.com/_/python
ARG PYTHON_VERSION=3.12
FROM python:"${PYTHON_VERSION}"-slim

ARG CODE_LOCATION

# set shell to bash
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# set container envs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH=/app/.venv/bin:"${PATH}"

# set workdir
WORKDIR /app

# install uv & create venv
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install "uv==0.4.13" --no-cache-dir \
    && uv venv

# install dependencies
COPY pyproject.toml requirements.txt overrides.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    uv pip install \
    -r requirements.txt \
    --override overrides.txt \
    --no-cache-dir

# install python project
COPY src/teamster/ ./src/teamster/
RUN uv pip install \
    -e . \
    --override overrides.txt \
    --no-cache-dir

# install dbt project
COPY src/dbt/ ./src/dbt/
RUN dagster-dbt project prepare-and-package \
    --file src/teamster/code_locations/"${CODE_LOCATION}"/__init__.py