from dagster import ResourceParam, SensorEvaluationContext, sensor
from dagster_ssh import SSHResource


@sensor()
def foo(context: SensorEvaluationContext, sftp_renlearn: ResourceParam[SSHResource]):
    conn = sftp_renlearn.get_connection()

    with conn.open_sftp() as sftp_client:
        ls = sftp_client.listdir_attr()

    conn.close()

    for f in ls:
        context.log.info(f.filename, f.st_mtime)
