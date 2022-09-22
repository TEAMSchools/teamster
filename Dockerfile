# trunk-ignore(hadolint/DL3007)
FROM us-central1-docker.pkg.dev/teamster-332318/teamster-deps/teamster-deps:latest

WORKDIR $HOME/app
COPY teamster/ ./teamster/
