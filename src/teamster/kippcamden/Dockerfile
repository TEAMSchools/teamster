# Debian
FROM python:3.11-slim

# update system pip
# trunk-ignore(hadolint/DL3013)
RUN python -m pip install --no-cache-dir --upgrade pip

WORKDIR /root/app

# install dependencies & project
COPY pyproject.toml ./pyproject.toml
COPY src/teamster ./src/teamster
RUN pip install --no-cache-dir .

# install dbt
COPY src/dbt ./src/dbt
ENV DBT_PROFILES_DIR=/root/app/src/dbt/kippcamden
WORKDIR /root/app/src/dbt/kippcamden
RUN dbt clean && dbt deps && dbt parse

WORKDIR /root/app