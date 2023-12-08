# Debian
FROM python:3.11-slim

ENV DBT_PROFILES_DIR=/root/app/src/dbt/staging

# update system pip
# trunk-ignore(hadolint/DL3013)
RUN python -m pip install --no-cache-dir --upgrade pip

WORKDIR /root/app

# install dependencies & project
COPY src ./src
COPY pyproject.toml ./pyproject.toml
RUN pip install --no-cache-dir .

# install dbt
WORKDIR /root/app/src/dbt/staging
RUN dbt clean && dbt deps && dbt parse

WORKDIR /root/app