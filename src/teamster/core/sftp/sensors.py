from dagster import AssetsDefinition
from teamster.core.sftp.assets import listdir_attr_r
from teamster.core.ssh.resources import SSHConfigurableResource


def get_sftp_ls(ssh: SSHConfigurableResource, asset_defs: list[AssetsDefinition]):
    ls = {}

    with ssh.get_connection() as conn:
        with conn.open_sftp() as sftp_client:
            for asset in asset_defs:
                ls[asset.key.to_python_identifier()] = {
                    "asset": asset,
                    "files": listdir_attr_r(
                        sftp_client=sftp_client,
                        remote_dir=asset.metadata_by_key[asset.key]["remote_dir"],
                    ),
                }

    return ls
