import os

SQLALCHEMY_DATABASE_URI = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://superset:superset@superset-db:5432/superset",
)
SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "change-me-for-production")
PREVENT_UNSAFE_DB_CONNECTIONS = False
