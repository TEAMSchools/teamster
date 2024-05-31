from dagster import EnvVar, build_init_resource_context

from teamster.core.ssh.resources import SSHResource


def test_listdir_attr_r_test():
    SSH_COUCHDROP = SSHResource(
        remote_host=EnvVar("COUCHDROP_SFTP_HOST").get_value(),
        username=EnvVar("COUCHDROP_SFTP_USERNAME").get_value(),
        password=EnvVar("COUCHDROP_SFTP_PASSWORD").get_value(),
    )

    SSH_COUCHDROP.setup_for_execution(context=build_init_resource_context())

    files = SSH_COUCHDROP.listdir_attr_r_test(remote_dir="data-team")

    for f in files:
        print(f.filename)
