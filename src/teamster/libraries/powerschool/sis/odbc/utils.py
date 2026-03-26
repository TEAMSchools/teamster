"""PowerSchool SIS ODBC shared utilities.

Context managers, timestamp formatting, partition window calculation,
and staleness evaluation logic shared across assets, schedules, and sensors.
"""

from sqlalchemy import text


def get_query_text(
    table: str,
    column: str | None,
    start_value: str | None = None,
    end_value: str | None = None,
):
    """Build a SQLAlchemy text clause for an Oracle COUNT query.

    Args:
        table: Oracle table name.
        column: Column to filter on. None for full table count.
        start_value: ISO timestamp string for >= or BETWEEN start.
        end_value: ISO timestamp string for BETWEEN end. Requires start_value.

    Returns:
        SQLAlchemy TextClause wrapping the COUNT query.
    """
    # TODO: paramterize sqlalchemy query to resolve bandit/B608
    if column is None:
        # trunk-ignore(bandit/B608)
        query = f"SELECT COUNT(*) FROM {table}"
    elif end_value is None:
        query = (
            # trunk-ignore(bandit/B608)
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE {column} >= "
            f"TO_TIMESTAMP('{start_value}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
        )
    else:
        query = (
            # trunk-ignore(bandit/B608)
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE {column} BETWEEN "
            f"TO_TIMESTAMP('{start_value}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6') AND "
            f"TO_TIMESTAMP('{end_value}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
        )

    return text(query)
