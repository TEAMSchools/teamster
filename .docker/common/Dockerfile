ARG IMAGE_PYTHON_VERSION="3.10"

# Debian Bullseye
FROM python:${IMAGE_PYTHON_VERSION}-slim

# install system deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the SHELL option -o pipefail before RUN with a pipe in
# https://github.com/codacy/codacy-hadolint/blob/a762bbf9decbe11c111e898fdee6dcb3f11a656b/codacy-hadolint/docs/description/DL4006.md
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# install Microsoft ODBC driver for SQL Server
# https://docs.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server?view=sql-server-ver16#debian18
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
RUN curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list

RUN apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# # install pdm
RUN curl -sSL https://raw.githubusercontent.com/pdm-project/pdm/main/install-pdm.py | python3 -
ENV PATH="/root/.local/bin:$PATH"

# copy project into container
ENV HOME="/root"
WORKDIR $HOME/app
COPY . $HOME/app

# # install project dependencies
RUN pdm config python.use_venv False
RUN pdm install --prod --no-lock --no-editable

# add pdm directories to PATH envars
ARG IMAGE_PYTHON_VERSION
ENV PYTHONPATH="/root/app/__pypackages__/${IMAGE_PYTHON_VERSION}/lib"
ENV PATH="/root/app/__pypackages__/${IMAGE_PYTHON_VERSION}/bin:$PATH"
