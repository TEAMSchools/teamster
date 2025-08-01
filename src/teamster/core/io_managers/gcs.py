from datetime import datetime
from urllib.parse import urlparse

import fastavro
from dagster import Any, InputContext, MultiPartitionKey, OutputContext
from dagster._utils.backoff import backoff
from dagster_gcp.gcs import GCSPickleIOManager, PickledObjectGCSIOManager
from dagster_shared.utils.cached_method import cached_method
from google.api_core.exceptions import Forbidden, ServiceUnavailable, TooManyRequests
from google.cloud.storage import Bucket
from upath import UPath

from teamster.core.utils.classes import FiscalYear


class GCSUPathIOManager(PickledObjectGCSIOManager):
    def _parse_datetime_partition_value(self, partition_value: str):
        datetime_formats = iter(["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%m/%d/%Y"])
        while True:
            try:
                return datetime.strptime(partition_value, next(datetime_formats))
            except ValueError:
                pass

    def _get_hive_partition(
        self, partition_value: str, partition_key: str = "key"
    ) -> str:
        try:
            datetime = self._parse_datetime_partition_value(partition_value)
            return "/".join(
                [
                    "_dagster_partition_fiscal_year="
                    + str(FiscalYear(datetime=datetime, start_month=7).fiscal_year),
                    f"_dagster_partition_date={datetime.date().isoformat()}",
                    f"_dagster_partition_hour={datetime.strftime('%H')}",
                    f"_dagster_partition_minute={datetime.strftime('%M')}",
                ]
            )
        except StopIteration:
            return f"_dagster_partition_{partition_key}={partition_value}"

    def _formatted_multipartitioned_path(self, partition_key: MultiPartitionKey) -> str:
        ordered_dimension_keys = []

        for key, value in sorted(
            partition_key.keys_by_dimension.items(), key=lambda x: x[0]
        ):
            ordered_dimension_keys.append(
                self._get_hive_partition(partition_key=key, partition_value=value)
            )

        return "/".join(ordered_dimension_keys)

    def _get_paths_for_partitions(
        self, context: InputContext | OutputContext
    ) -> dict[str, UPath]:
        if not context.has_asset_partitions:
            raise TypeError(
                f"Detected {context.dagster_type.typing_type} input type but the asset"
                " is not partitioned"
            )

        formatted_partition_keys = {
            partition_key: (
                self._formatted_multipartitioned_path(partition_key)
                if isinstance(partition_key, MultiPartitionKey)
                else self._get_hive_partition(partition_value=partition_key)
            )
            for partition_key in context.asset_partition_keys
        }

        return {
            partition_key: self._with_extension(
                self.get_path_for_partition(
                    context=context,
                    path=self._get_path_without_extension(context),
                    partition=partition,
                )
            )
            / "data"
            for partition_key, partition in formatted_partition_keys.items()
        }

    def _get_path(self, context: InputContext | OutputContext) -> UPath:
        return super()._get_path(context) / "data"


class AvroGCSIOManager(GCSUPathIOManager):
    def __init__(
        self,
        bucket: str,
        client: Any | None = None,
        prefix: str = "dagster",
        test: bool = False,
    ):
        self.test = test

        super().__init__(bucket, client, prefix)

    def load_from_path(self, context: InputContext, path: UPath) -> Any:
        blob = self.bucket_obj.blob(blob_name=str(path))

        with blob.open(mode="rb") as fo:
            # trunk-ignore(pyright/reportArgumentType)
            reader = fastavro.reader(fo=fo)

            records = [record for record in reader]

        return (records, reader.writer_schema)

    def dump_to_path(self, context: OutputContext, obj: Any, path: UPath) -> None:
        bucket_obj: Bucket = self.bucket_obj

        records, schema = obj
        local_path = "env" / path

        if self.test:
            import json

            test_path = "env/test" / path.with_suffix(".json")

            test_path.parent.mkdir(parents=True, exist_ok=True)
            json.dump(obj=records, fp=test_path.open("w"))

        context.log.info(f"Writing records to {local_path}")
        local_path.parent.mkdir(parents=True, exist_ok=True)

        with local_path.open(mode="wb") as fo:
            fastavro.writer(
                fo=fo,
                schema=fastavro.parse_schema(schema),
                records=records,
                codec="snappy",
            )

        if self.path_exists(path):
            context.log.warning(f"Existing GCS key: {path}")

        backoff(
            fn=bucket_obj.blob(blob_name=str(path)).upload_from_filename,
            retry_on=(TooManyRequests, Forbidden, ServiceUnavailable),
            kwargs={"filename": local_path},
        )


class FileGCSIOManager(GCSUPathIOManager):
    def load_from_path(self, context: InputContext, path: UPath) -> Any:
        return urlparse(self._uri_for_path(path))

    def dump_to_path(self, context: OutputContext, obj: Any, path: UPath) -> None:
        bucket_obj: Bucket = self.bucket_obj

        if self.path_exists(path):
            context.log.warning(f"Removing existing GCS key: {path}")
            self.unlink(path)

        backoff(
            fn=bucket_obj.blob(blob_name=str(path)).upload_from_filename,
            retry_on=(TooManyRequests, Forbidden, ServiceUnavailable),
            kwargs={"filename": obj},
        )


class GCSIOManager(GCSPickleIOManager):
    object_type: str
    test: bool = False

    @property
    @cached_method
    def _internal_io_manager(
        self,
    ) -> AvroGCSIOManager | PickledObjectGCSIOManager | None:
        if self.object_type == "avro":
            return AvroGCSIOManager(
                bucket=self.gcs_bucket,
                client=self.gcs.get_client(),
                prefix=self.gcs_prefix,
                test=self.test,
            )
        if self.object_type == "file":
            return FileGCSIOManager(
                bucket=self.gcs_bucket,
                client=self.gcs.get_client(),
                prefix=self.gcs_prefix,
            )
        elif self.object_type == "pickle":
            return PickledObjectGCSIOManager(
                bucket=self.gcs_bucket,
                client=self.gcs.get_client(),
                prefix=self.gcs_prefix,
            )
