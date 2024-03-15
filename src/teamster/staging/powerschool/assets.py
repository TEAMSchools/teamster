from dagster import file_relative_path
from dagster_embedded_elt.sling import (
    DagsterSlingTranslator,
    SlingResource,
    sling_assets,
)

from teamster.core.ssh.resources import SSHResource

replication_config = file_relative_path(
    dunderfile=__file__, relative_path="replication.yaml"
)


@sling_assets(replication_config=replication_config)
def powerschool_table_assets(
    context, ssh_powerschool: SSHResource, sling: SlingResource
):
    ssh_tunnel = ssh_powerschool.get_tunnel(remote_port=1521, local_port=1521)

    try:
        context.log.info("Starting SSH tunnel")
        ssh_tunnel.start()

        yield from sling.replicate(
            replication_config=replication_config,
            dagster_sling_translator=DagsterSlingTranslator(),
            # debug=True,
        )

        for row in sling.stream_raw_logs():
            context.log.info(row)
    finally:
        context.log.info("Stopping SSH tunnel")
        ssh_tunnel.stop()
