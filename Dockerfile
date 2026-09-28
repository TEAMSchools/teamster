# https://docs.astral.sh/uv/guides/integration/docker/
# named stage so Dependabot's docker ecosystem can bump the pin
FROM ghcr.io/astral-sh/uv:0.12.19 AS uv

# https://hub.docker.com/_/python
FROM python:3.13-slim
ARG CODE_LOCATION

# set container envs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:${PATH}"
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1
ENV UV_NO_CACHE=1

# create non-root user
RUN groupadd -g 1234 teamster \
    && useradd -m -u 1234 -g teamster teamster

# switch to the non-root user
USER 1234:1234

# set workdir
WORKDIR /app

# install uv
COPY --from=uv /uv /bin/

# copy & install python deps
COPY --chown=1234:1234 uv.lock pyproject.toml /app/
RUN uv sync --frozen --no-dev --no-install-project --no-editable

# copy & install dagster project
COPY --chown=1234:1234 src/teamster/ /app/src/teamster/
RUN uv sync --frozen --no-dev --no-editable

# copy & install dbt project
COPY --chown=1234:1234 src/dbt/ /app/src/dbt/
RUN dagster-dbt project prepare-and-package \
    --file "src/teamster/code_locations/${CODE_LOCATION}/__init__.py"
