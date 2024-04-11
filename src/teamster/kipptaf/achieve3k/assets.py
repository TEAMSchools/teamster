from dagster import DynamicPartitionsDefinition

from teamster.core.sftp.assets import build_sftp_asset

from .. import CODE_LOCATION
from .schema import ASSET_SCHEMA

students = build_sftp_asset(
    asset_key=[CODE_LOCATION, "achieve3k", "students"],
    remote_dir="outgoing",
    remote_file_regex=r"(?P<date>\d{4}[-\d{2}]+)-\d+_D[\d+_]+(\w\d{4}[-\d{2}]+_){2}student\.\w+",
    ssh_resource_key="ssh_achieve3k",
    avro_schema=ASSET_SCHEMA["students"],
    partitions_def=DynamicPartitionsDefinition(
        name=f"{CODE_LOCATION}__achieve3k__students"
    ),
)

_all = [
    students,
]
