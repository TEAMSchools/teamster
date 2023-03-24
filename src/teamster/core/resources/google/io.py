import copy
import pathlib
import pickle
from urllib.parse import urlparse

import fastavro
from dagster import Field, InputContext, IOManager, OutputContext, String, StringSource
from dagster import _check as check
from dagster import io_manager
from dagster._utils import PICKLE_PROTOCOL
from dagster._utils.backoff import backoff
from google.api_core.exceptions import Forbidden, ServiceUnavailable, TooManyRequests
from google.cloud import storage

from teamster.core.utils.functions import get_partition_key_path


class GCSIOManager(IOManager):
    def __init__(self, bucket, client=None, prefix="dagster"):
        self.bucket = check.str_param(bucket, "bucket")
        self.client = client or storage.Client()
        self.bucket_obj = self.client.bucket(bucket)
        check.invariant(self.bucket_obj.exists())
        self.prefix = check.str_param(prefix, "prefix")

    def _get_paths(self, context: InputContext | OutputContext) -> list[str]:
        if context.has_asset_key:
            if context.has_asset_partitions:
                paths = []
                for key in context.asset_partition_keys:
                    path = get_partition_key_path(
                        partition_key=key, path=copy.deepcopy(context.asset_key.path)
                    )

                    paths.append("/".join([self.prefix, *path]))
                return paths
            else:
                path = copy.deepcopy(context.asset_key.path)

                path.append("data")

                return ["/".join([self.prefix, *path])]
        else:
            parts = context.get_identifier()

            run_id = parts[0]
            output_parts = parts[1:]

            path = ["storage", run_id, "files", *output_parts]

            return ["/".join([self.prefix, *path])]

    def _rm_object(self, key):
        check.str_param(key, "key")
        check.param_invariant(len(key) > 0, "key")

        if self.bucket_obj.blob(key).exists():
            self.bucket_obj.blob(key).delete()

    def _has_object(self, key):
        check.str_param(key, "key")
        check.param_invariant(len(key) > 0, "key")
        blobs = self.client.list_blobs(self.bucket, prefix=key)
        return len(list(blobs)) > 0

    def _uri_for_key(self, key):
        check.str_param(key, "key")
        return "gs://" + self.bucket + "/" + "{key}".format(key=key)


class FilepathGCSIOManager(GCSIOManager):
    def handle_output(self, context: OutputContext, file_path: pathlib.Path):
        for path in self._get_paths(context):
            if self._has_object(path):
                context.log.warning(f"Removing existing GCS key: {path}")
                self._rm_object(path)

            context.log.info(
                f"Uploading {file_path} to GCS object at: {self._uri_for_key(path)}"
            )

            backoff(
                self.bucket_obj.blob(path).upload_from_filename,
                args=[file_path],
                retry_on=(TooManyRequests, Forbidden, ServiceUnavailable),
            )

    def load_input(self, context: InputContext):
        if isinstance(context.dagster_type.typing_type, type(None)):
            return None

        paths = self._get_paths(context)

        return [urlparse(self._uri_for_key(path)) for path in paths]


class AvroGCSIOManager(GCSIOManager):
    def handle_output(self, context: OutputContext, obj: tuple):
        records, schema = obj

        for path in self._get_paths(context):
            if self._has_object(path):
                context.log.warning(f"Removing existing GCS key: {path}")
                self._rm_object(path)

            file_path = pathlib.Path(path)

            context.log.debug(f"Saving output to Avro file: {file_path}")
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with file_path.open(mode="wb") as fo:
                fastavro.writer(
                    fo=fo,
                    schema=fastavro.parse_schema(schema),
                    records=records,
                    codec="snappy",
                )

            context.log.info(
                f"Uploading {file_path} to GCS object at: {self._uri_for_key(path)}"
            )

            backoff(
                self.bucket_obj.blob(path).upload_from_filename,
                args=[file_path],
                retry_on=(TooManyRequests, Forbidden, ServiceUnavailable),
            )

    def load_input(self, context: InputContext):
        if isinstance(context.dagster_type.typing_type, type(None)):
            return None

        paths = self._get_paths(context)

        return [urlparse(self._uri_for_key(path)) for path in paths]


class PickledObjectGCSIOManager(GCSIOManager):
    def load_input(self, context):
        if context.dagster_type.typing_type == type(None):
            return None

        for path in self._get_paths(context):
            context.log.debug(f"Loading GCS object from: {self._uri_for_key(path)}")

            bytes_obj = self.bucket_obj.blob(path).download_as_bytes()
            obj = pickle.loads(bytes_obj)

            yield obj

    def handle_output(self, context, obj):
        if context.dagster_type.typing_type == type(None):
            check.invariant(
                obj is None,
                (
                    "Output had Nothing type or 'None' annotation, but handle_output "
                    f"received value that was not None and was of type {type(obj)}."
                ),
            )
            return None

        for path in self._get_paths(context):
            context.log.debug(f"Writing GCS object at: {self._uri_for_key(path)}")

            if self._has_object(path):
                context.log.warning(f"Removing existing GCS key: {path}")
                self._rm_object(path)

            pickled_obj = pickle.dumps(obj, PICKLE_PROTOCOL)

            backoff(
                self.bucket_obj.blob(path).upload_from_string,
                args=[pickled_obj],
                retry_on=(TooManyRequests, Forbidden, ServiceUnavailable),
            )


@io_manager(
    config_schema={
        "io_format": Field(config=String),
        "gcs_bucket": Field(config=StringSource),
        "gcs_prefix": Field(
            config=StringSource, is_required=False, default_value="dagster"
        ),
    },
    required_resource_keys={"gcs"},
)
def gcs_io_manager(init_context):
    client = init_context.resources.gcs
    bucket = init_context.resource_config["gcs_bucket"]
    prefix = init_context.resource_config["gcs_prefix"]
    io_format = init_context.resource_config["io_format"]

    if io_format == "filepath":
        return FilepathGCSIOManager(bucket=bucket, client=client, prefix=prefix)
    elif io_format == "avro":
        return AvroGCSIOManager(bucket=bucket, client=client, prefix=prefix)
    elif io_format == "pickle":
        return PickledObjectGCSIOManager(bucket=bucket, client=client, prefix=prefix)
