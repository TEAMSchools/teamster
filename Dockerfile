# trunk-ignore-all(trivy/DS026,checkov/CKV_DOCKER_2)
ARG PYTHON_VERSION

# Debian
FROM python:${PYTHON_VERSION}-slim

ARG CODE_LOCATION
ENV DBT_PROFILES_DIR=/root/app/src/dbt/${CODE_LOCATION}

WORKDIR /root/app

# update system pip
# trunk-ignore(hadolint/DL3013,terrascan/AC_DOCKER_0010)
RUN python -m pip install pip --no-cache-dir --upgrade

# install dependencies & project
COPY pyproject.toml ./pyproject.toml
RUN pip install . --no-cache-dir

# install project
COPY src ./src
RUN pip install . --no-cache-dir

# install dbt
WORKDIR ${DBT_PROFILES_DIR}
RUN dbt clean && dbt deps && dbt parse

WORKDIR /root/app