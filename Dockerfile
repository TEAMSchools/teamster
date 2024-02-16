# https://hub.docker.com/_/python
ARG PYTHON_VERSION
FROM python:"${PYTHON_VERSION}"-slim

# set shell to bash
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# set dbt env from build arg
ARG CODE_LOCATION
ENV DBT_PROFILES_DIR /app/src/dbt/"${CODE_LOCATION}"

# set container envs
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PATH /app/.venv/bin:"${PATH}"

# set workdir
WORKDIR /app

# install uv & create venv
RUN pip install "uv<1" --no-cache-dir \
    && uv venv

# install dependencies
COPY pyproject.toml requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    uv pip install -r requirements.txt --no-cache-dir

# install python project
COPY src/teamster/ ./src/teamster/
RUN uv pip install -e . --no-cache-dir

# install dbt project
COPY src/dbt/ ./src/dbt/
RUN dbt clean --project-dir "${DBT_PROFILES_DIR}" \
    && dbt deps --project-dir "${DBT_PROFILES_DIR}" \
    && dbt parse --project-dir "${DBT_PROFILES_DIR}"