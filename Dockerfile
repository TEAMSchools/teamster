ARG PYTHON_VERSION=3.12

# https://hub.docker.com/_/python
FROM python:"${PYTHON_VERSION}-slim"
ARG CODE_LOCATION

# set container envs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:${PATH}"
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1

# trunk-ignore(hadolint/DL3008)
RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client sshpass \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# set workdir
WORKDIR /app

# Create a custom user with UID 1234 and GID 1234
RUN groupadd -g 1234 teamster \
    && useradd -m -u 1234 -g teamster teamster \
    && chown -R 1234:1234 /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/
COPY uv.lock pyproject.toml /app/

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --no-editable

# Copy the project into the image
COPY src/ /app/src/

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# Install dbt project
RUN dagster-dbt project prepare-and-package \
    --file "src/teamster/code_locations/${CODE_LOCATION}/__init__.py"

# Switch to the custom user
USER 1234:1234