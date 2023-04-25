from dagster import config_from_files

from teamster.core.renlearn.sensors import build_sftp_sensor

from .. import CODE_LOCATION

local_config_dir = f"src/teamster/{CODE_LOCATION}/config/assets/renlearn"

sftp_sensor = build_sftp_sensor(
    code_location=CODE_LOCATION,
    asset_configs=config_from_files([f"{local_config_dir}/assets.yaml"])["assets"],
)

__all__ = [
    sftp_sensor,
]
