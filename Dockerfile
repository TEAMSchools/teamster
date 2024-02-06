ARG PYTHON_VERSION

# Debian
FROM python:${PYTHON_VERSION}-slim

ARG CODE_LOCATION

# set container envs
ENV DBT_PROFILES_DIR=/app/src/dbt/${CODE_LOCATION}
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# install dependencies & project
COPY pyproject.toml ./pyproject.toml
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install . --no-cache-dir

# install python project
COPY src/teamster/ ./src/teamster/
RUN pip install . --no-cache-dir

# install dbt project
COPY src/dbt/ ./src/dbt/
WORKDIR ${DBT_PROFILES_DIR}
RUN dbt clean && dbt deps && dbt parse

WORKDIR /app