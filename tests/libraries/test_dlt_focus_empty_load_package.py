"""The empty-table load package carries the reflected columns, not just `_dlt_*`.

If `materialize_table_schema()` reached dlt before the reflection hints, the
created BigQuery table would hold only `_dlt_load_id` and `_dlt_id`, and every
later load would have to ADD the real columns. This asserts the emitted parquet
already has them.

Extract plus normalize only — no BigQuery credentials are used.
"""

import shutil
import tempfile
from pathlib import Path

import dlt
import pyarrow.parquet as pq
import sqlalchemy as sa
from dlt import config as dlt_config
from dlt.common.configuration.specs import ConnectionStringCredentials
from dlt.destinations import bigquery

from teamster.libraries.dlt.focus.assets import build_focus_source


def test_empty_table_package_carries_reflected_columns(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'focus.db'}"
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "create table referrals ("
                "referral_id integer not null, comment text, entry_date date)"
            )
        )
    engine.dispose()

    dlt_config["normalize.parquet_normalizer.add_dlt_id"] = True
    dlt_config["normalize.parquet_normalizer.add_dlt_load_id"] = True

    pipelines_dir = tempfile.mkdtemp(prefix="focus-empty-")
    try:
        pipeline = dlt.pipeline(
            pipeline_name="focus_empty_package_test",
            destination=bigquery(autodetect_schema=True),
            dataset_name="test",
            pipelines_dir=pipelines_dir,
        )

        pipeline.extract(
            build_focus_source(
                sql_database_credentials=ConnectionStringCredentials(url),
                table_name="referrals",
                db_schema=None,
            ),
            loader_file_format="parquet",
        )
        pipeline.normalize()

        package = pipeline.list_normalized_load_packages()[-1]
        info = pipeline.get_load_package_info(package)

        jobs = [
            j
            for j in info.jobs["new_jobs"]
            if j.job_file_info.table_name == "referrals"
        ]

        assert len(jobs) == 1, "the empty table must produce exactly one job"

        path = Path(jobs[0].file_path)
        assert path.suffix == ".parquet"

        names = pq.read_schema(path).names

        assert "referral_id" in names
        assert "comment" in names
        assert "entry_date" in names
        assert "_dlt_load_id" in names
        assert "_dlt_id" in names
    finally:
        shutil.rmtree(pipelines_dir, ignore_errors=True)
        dlt_config["normalize.parquet_normalizer.add_dlt_id"] = False
        dlt_config["normalize.parquet_normalizer.add_dlt_load_id"] = False
