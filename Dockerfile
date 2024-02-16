# https://hub.docker.com/_/python
ARG PYTHON_VERSION
FROM python:"${PYTHON_VERSION}"-slim

# set shell to bash
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# set container envs
ARG CODE_LOCATION
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DBT_PROFILES_DIR /app/src/dbt/"${CODE_LOCATION}"
ENV PATH /root/.venv/bin:/root/.cargo/bin:"${PATH}"

# install curl & uv
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl=* \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && uv venv

# set workdir
WORKDIR /app

# install dependencies
COPY pyproject.toml requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    uv pip install -r requirements.txt --no-cache-dir

# install python project
COPY src/teamster/ ./src/teamster/
RUN uv pip install . --no-cache-dir

# install dbt project
COPY src/dbt/ ./src/dbt/
RUN dbt clean --project-dir "${DBT_PROFILES_DIR}" \
    && dbt deps --project-dir "${DBT_PROFILES_DIR}" \
    && dbt parse --project-dir "${DBT_PROFILES_DIR}"