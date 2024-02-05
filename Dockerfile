# trunk-ignore-all(checkov)
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

# install dbt project
COPY src/dbt ./src/dbt
WORKDIR ${DBT_PROFILES_DIR}
RUN dbt clean && dbt deps && dbt parse

# install python project
WORKDIR /root/app
COPY src/teamster ./src/teamster
RUN pip install . --no-cache-dir