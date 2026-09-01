"""Translation between i-Ready partition subjects and vendor filename tokens.

Curriculum Associates renamed the reading exports from `ela` to `reading` for
FY2027. The partition subject stays `ela` in every fiscal year, because the GCS
object path is derived from the partition key and `MultiPartitionsDefinition` is
a cartesian product that cannot vary its subject list by year. So the rename is
absorbed here, at the SFTP boundary, in both directions.
"""

# partition key of FY2027, the first year the vendor used the new export names
RENAME_ACADEMIC_YEAR = 2026

# partition subject -> filename token, for FY2027 and later
REMOTE_SUBJECT_TOKENS = {"ela": "reading"}

PARTITION_SUBJECTS_BY_REMOTE_TOKEN = {
    token: subject for subject, token in REMOTE_SUBJECT_TOKENS.items()
}


def is_legacy_year(academic_year: str) -> bool:
    """True when this partition's files still carry the pre-FY2027 names.

    `Current_Year` is the vendor's folder for the newest fiscal year, so it is
    never legacy.
    """
    if academic_year == "Current_Year":
        return False

    return int(academic_year) < RENAME_ACADEMIC_YEAR


def remote_subject_token(subject: str, academic_year: str) -> str:
    """Partition subject -> the token that appears in the filename."""
    if is_legacy_year(academic_year):
        return subject

    return REMOTE_SUBJECT_TOKENS.get(subject, subject)


def partition_subject(remote_token: str, academic_year: str) -> str:
    """Filename token -> the partition subject it belongs to.

    A stale pre-rename file left behind in `Current_Year` still maps to its
    original partition, so it can trigger a run but never becomes the payload.
    """
    if is_legacy_year(academic_year):
        return remote_token

    return PARTITION_SUBJECTS_BY_REMOTE_TOKEN.get(remote_token, remote_token)
