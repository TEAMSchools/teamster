ARG PYTHON_VERSION

# Debian
FROM python:${PYTHON_VERSION}-slim

ARG CODE_LOCATION

# set container envs
ENV DBT_PROFILES_DIR=/app/src/dbt/${CODE_LOCATION}
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# set workdir
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
RUN dbt clean \
    && dbt deps --project-dir ${DBT_PROFILES_DIR} \
    && dbt parse --project-dir ${DBT_PROFILES_DIR}

# create non-root user
RUN groupadd -r app && useradd -r -g app app
USER app