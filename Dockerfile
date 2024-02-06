ARG PYTHON_VERSION

# Debian
FROM python:${PYTHON_VERSION}-slim

ARG CODE_LOCATION

# create non-root user
RUN useradd -ms /bin/sh app
USER app

# set container envs
ENV PATH=${PATH}:/home/app/.local/bin
ENV DBT_PROFILES_DIR=/home/app/src/dbt/${CODE_LOCATION}
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /home/app

# install dependencies & project
COPY pyproject.toml ./pyproject.toml
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install . --no-cache-dir

# install python project
WORKDIR /home/app
COPY src/teamster/ ./src/teamster/
RUN pip install . --no-cache-dir

# install dbt project
COPY src/dbt/ ./src/dbt/
WORKDIR ${DBT_PROFILES_DIR}
RUN dbt clean && dbt deps && dbt parse

WORKDIR /home/app