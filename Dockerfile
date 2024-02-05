ARG PYTHON_VERSION

# Debian
FROM python:${PYTHON_VERSION}-slim

ARG CODE_LOCATION
ENV DBT_PROFILES_DIR=/root/app/src/dbt/${CODE_LOCATION}

RUN apt-get update && apt-get -y install build-essential --no-install-recommends \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# update system pip
# hadolint ignore=DL3013
RUN python -m pip install --no-cache-dir --upgrade pip

WORKDIR /root/app

# install dependencies & project
COPY src ./src
COPY pyproject.toml ./pyproject.toml
RUN pip install --no-cache-dir .

# install dbt
WORKDIR ${DBT_PROFILES_DIR}
RUN dbt clean && dbt deps && dbt parse

WORKDIR /root/app