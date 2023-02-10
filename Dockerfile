# Debian
FROM python:3.10-slim

# update system pip
# trunk-ignore(hadolint/DL3013)
RUN python -m pip install --no-cache-dir --upgrade pip

# install system deps
# trunk-ignore(hadolint/DL3008)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl gnupg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# install Microsoft ODBC driver for SQL Server (Debian 11)
# https://docs.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server?view=sql-server-ver16#debian18
# set the SHELL option -o pipefail before RUN with a pipe in
# https://github.com/codacy/codacy-hadolint/blob/a762bbf9decbe11c111e898fdee6dcb3f11a656b/codacy-hadolint/docs/description/DL4006.md
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
RUN curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list
# trunk-ignore(hadolint/DL3008)
RUN apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# copy requirements files into container
WORKDIR /root/app
COPY requirements.txt ./requirements.txt
COPY pyproject.toml ./pyproject.toml

# install project reqs
RUN pip install --no-cache-dir -r requirements.txt

# install project
COPY src/teamster ./src/teamster
RUN pip install --no-cache-dir .

# install dbt deps
COPY teamster-dbt ./teamster-dbt
RUN dbt deps --project-dir teamster-dbt/kippcamden \
    && dbt list \
        --project-dir teamster-dbt/kippcamden \
        --profiles-dir teamster-dbt/kippcamden
