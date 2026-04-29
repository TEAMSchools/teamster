FROM apache/superset:4.1.1

USER root

RUN pip install --no-cache-dir sqlalchemy-bigquery

COPY superset_config.py /app/pythonpath/superset_config.py
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER superset

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
