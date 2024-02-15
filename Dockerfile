# https://hub.docker.com/_/python
ARG PYTHON_VERSION
FROM python:${PYTHON_VERSION}-slim

# install system dependencies
# trunk-ignore(hadolint/DL3008)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# install rust
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

# set container envs
ARG CODE_LOCATION
ENV PATH /root/.cargo/bin:${PATH}
ENV DBT_PROFILES_DIR /app/src/dbt/${CODE_LOCATION}
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# set workdir
WORKDIR /app

# install dependencies
COPY pyproject.toml requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt --no-cache-dir

# install python project
COPY src/teamster/ ./src/teamster/
RUN pip install . --no-cache-dir

# install dbt project
COPY src/dbt/ ./src/dbt/
RUN dbt clean --project-dir "${DBT_PROFILES_DIR}" \
    && dbt deps --project-dir "${DBT_PROFILES_DIR}" \
    && dbt parse --project-dir "${DBT_PROFILES_DIR}"