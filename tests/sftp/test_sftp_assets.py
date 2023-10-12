from dagster import EnvVar, build_asset_context

from teamster.core.ssh.resources import SSHConfigurableResource


def test_assets_renlearn_kippmiami():
    from teamster.kippmiami.renlearn import assets

    for asset in assets:
        asset(
            context=build_asset_context(
                resources={
                    "ssh_renlearn": SSHConfigurableResource(
                        remote_host="sftp.renaissance.com",
                        username=EnvVar("KIPPMIAMI_RENLEARN_SFTP_USERNAME"),
                        password=EnvVar("KIPPMIAMI_RENLEARN_SFTP_PASSWORD"),
                    )
                }
            )
        )
