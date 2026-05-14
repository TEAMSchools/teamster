# syntax=docker/dockerfile:1.7

FROM python:3.13-slim AS base

# Install uv (used to install PEP 723 inline deps at run time).
RUN pip install --no-cache-dir uv==0.5.18

WORKDIR /app
COPY server.py /app/server.py

# Cloud Run sets PORT; our server reads TRANSPORT and binds 8080 explicitly.
EXPOSE 8080

# Use uv run to honor the PEP 723 inline dependency block at the top of server.py.
CMD ["uv", "run", "/app/server.py"]
