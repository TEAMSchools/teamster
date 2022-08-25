import pathlib

from dagster import In, RetryPolicy, Tuple, op


@op(
    ins={"transformed": In(dagster_type=Tuple)},
    tags={"dagster/priority": 4},
    required_resource_keys={"destination", "file_manager"},
    retry_policy=RetryPolicy(max_retries=2),
)
def load_destination(context, transformed):
    dest_config = transformed[0]

    dest_type = dest_config["type"]
    if dest_type == "gsheet":
        file_stem, df_dict = transformed[1:]
        context.resources.destination.update_named_range(
            data=df_dict, spreadsheet_name=file_stem, range_name=file_stem
        )
    elif dest_type == "sftp":
        file_handle = transformed[1]
        dest_path = dest_config.get("path")

        sftp_conn = context.resources.destination.get_connection()
        file_name = pathlib.Path(file_handle.gcs_key).name

        with sftp_conn.open_sftp() as sftp:
            sftp.chdir(".")

            if dest_path:
                dest_filepath = pathlib.Path(sftp.getcwd()) / dest_path / file_name
            else:
                dest_filepath = pathlib.Path(sftp.getcwd()) / file_name

            # confirm dest_filepath dir exists or create it
            try:
                sftp.stat(str(dest_filepath.parent))
            except IOError:
                dir_path = pathlib.Path("/")
                for dir in dest_filepath.parent.parts:
                    dir_path = dir_path / dir
                    try:
                        sftp.stat(str(dir_path))
                    except IOError:
                        context.log.info(f"Creating directory: {dir_path}")
                        sftp.mkdir(str(dir_path))

            # if dest_path given, chdir after confirming
            if dest_path:
                sftp.chdir(str(dest_filepath.parent))

            context.log.info(
                (
                    "Starting to transfer file from "
                    f"{file_handle.path_desc} to {dest_filepath}"
                )
            )

            with sftp.file(file_name, "w") as f:
                f.write(
                    context.resources.file_manager.read_data(file_handle=file_handle)
                )
