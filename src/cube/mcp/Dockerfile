# syntax=docker/dockerfile:1.7

FROM python:3.13-slim

# Build-time only: install uv to extract PEP 723 deps from server.py.
RUN pip install --no-cache-dir uv==0.11.14

WORKDIR /app
COPY server.py /app/server.py

# Extract PEP 723 inline deps from server.py and install to system Python.
# Single source of truth: deps live in server.py's PEP 723 block; this just
# replays them at build time so container start doesn't pay the install cost.
RUN uv export --script /app/server.py --no-hashes > /tmp/requirements.txt \
    && uv pip install --system --no-cache -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

EXPOSE 8080

CMD ["python", "/app/server.py"]
