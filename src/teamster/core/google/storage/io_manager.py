import fastavro
from dagster import Any, InputContext, OutputContext
from dagster._utils.backoff import backoff
from dagster._utils.cached_method import cached_method
from dagster_gcp.gcs import GCSPickleIOManager, PickledObjectGCSIOManager
from google.api_core.exceptions import Forbidden, ServiceUnavailable, TooManyRequests
from google.cloud import storage
from upath import UPath


class AvroGCSIOManager(PickledObjectGCSIOManager):
    def load_from_path(self, context: InputContext, path: UPath) -> Any:
        bucket_obj: storage.Bucket = self.bucket_obj

        return fastavro.reader(fo=bucket_obj.blob(str(path)).open("wb"))

    def dump_to_path(self, context: OutputContext, obj: Any, path: UPath) -> None:
        bucket_obj: storage.Bucket = self.bucket_obj
        records, schema = obj

        if self.path_exists(path):
            context.log.warning(f"Removing existing GCS key: {path}")
            self.unlink(path)

        backoff(
            fn=fastavro.writer,
            retry_on=(TooManyRequests, Forbidden, ServiceUnavailable),
            kwargs={
                "fo": bucket_obj.blob(str(path)).open(mode="wb"),
                "schema": fastavro.parse_schema(schema),
                "records": records,
                "codec": "snappy",
            },
        )


class GCSIOManager(GCSPickleIOManager):
    object_type: str

    @property
    @cached_method
    def _internal_io_manager(self) -> PickledObjectGCSIOManager:
        if self.object_type == "avro":
            return AvroGCSIOManager(
                bucket=self.gcs_bucket,
                client=self.gcs.get_client(),
                prefix=self.gcs_prefix,
            )
        else:
            return PickledObjectGCSIOManager(
                bucket=self.gcs_bucket,
                client=self.gcs.get_client(),
                prefix=self.gcs_prefix,
            )
