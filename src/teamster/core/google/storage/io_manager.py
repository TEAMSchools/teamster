from typing import Any, Dict, Union

from dagster import ConfigurableIOManager, InputContext, OutputContext, UPathIOManager
from dagster._core.execution.context.init import InitResourceContext
from dagster._utils.cached_method import cached_method
from dagster_gcp.gcs import PickledObjectGCSIOManager
from upath import UPath


class AvroGCSIOManager(UPathIOManager):
    def _get_paths_for_partitions(
        self, context: InputContext | OutputContext
    ) -> Dict[str, UPath]:
        return super()._get_paths_for_partitions(context)

    def _get_path(self, context: InputContext | OutputContext) -> UPath:
        return super()._get_path(context)

    def get_op_output_relative_path(
        self, context: Union[InputContext, OutputContext]
    ) -> UPath:
        parts = context.get_identifier()
        run_id = parts[0]
        output_parts = parts[1:]
        return UPath("storage", run_id, "files", *output_parts)

    def _uri_for_path(self, path: UPath) -> str:
        return f"gs://{self.bucket}/{path}"

    def load_from_path(self, context: InputContext, path: UPath) -> Any:
        bytes_obj = self.bucket_obj.blob(str(path)).download_as_bytes()
        return pickle.loads(bytes_obj)

    def dump_to_path(self, context: OutputContext, obj: Any, path: UPath) -> None:
        if self.path_exists(path):
            context.log.warning(f"Removing existing GCS key: {path}")
            self.unlink(path)

        pickled_obj = pickle.dumps(obj, PICKLE_PROTOCOL)

        backoff(
            self.bucket_obj.blob(str(path)).upload_from_string,
            args=[pickled_obj],
            retry_on=(TooManyRequests, Forbidden, ServiceUnavailable),
        )


class GCSIOManager(ConfigurableIOManager):
    def setup_for_execution(self, context: InitResourceContext) -> None:
        return super().setup_for_execution(context)

    @property
    @cached_method
    def _internal_io_manager(self) -> PickledObjectGCSIOManager:
        return PickledObjectGCSIOManager(
            bucket=self.gcs_bucket, client=self.gcs.get_client(), prefix=self.gcs_prefix
        )
