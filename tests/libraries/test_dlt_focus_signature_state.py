"""The Focus resource persists its probed signature to dlt resource state.

The signature must be written from INSIDE the extracted resource: dlt commits
state only from resources that actually reached the load package, so a write
from the source function body or after the load never round-trips. sqlite stands
in for Focus Postgres — the Codespace cannot reach Focus (IP allowlist).
"""

import shutil
import tempfile
from pathlib import Path

import dlt
import sqlalchemy as sa
from dlt import config as dlt_config
from dlt.common.configuration.specs import ConnectionStringCredentials
from dlt.destinations import bigquery

from teamster.libraries.dlt.focus.assets import build_focus_source
from teamster.libraries.dlt.probe import ProbeTable, stored_signatures

SIGNATURE = {"count": 3, "max_cursor": "2026-08-09T12:00:00"}


def _seed(url: str, rows: int) -> None:
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            sa.text("create table referrals (referral_id integer not null, note text)")
        )
        for i in range(rows):
            conn.execute(sa.text("insert into referrals values (:i, 'n')"), {"i": i})
    engine.dispose()


def _extract(url: str, rows: int, signature: dict) -> dict[str, dict]:
    """Extract one table through the real source and return the stored state."""
    _seed(url, rows)

    dlt_config["normalize.parquet_normalizer.add_dlt_id"] = True
    dlt_config["normalize.parquet_normalizer.add_dlt_load_id"] = True

    pipelines_dir = tempfile.mkdtemp(prefix="focus-signature-")
    try:
        pipeline = dlt.pipeline(
            pipeline_name="focus_signature_test",
            destination=bigquery(autodetect_schema=True),
            dataset_name="test",
            pipelines_dir=pipelines_dir,
        )
        pipeline.extract(
            build_focus_source(
                sql_database_credentials=ConnectionStringCredentials(url),
                tables=[ProbeTable(name="referrals", cursor_column="note")],
                signatures={"referrals": signature},
                db_schema=None,
            ),
            loader_file_format="parquet",
        )
        return stored_signatures(pipeline, "focus")
    finally:
        shutil.rmtree(pipelines_dir, ignore_errors=True)


def test_populated_table_persists_its_signature(tmp_path: Path) -> None:
    stored = _extract(f"sqlite:///{tmp_path / 'focus.db'}", rows=3, signature=SIGNATURE)

    assert stored == {"referrals": SIGNATURE}


def test_empty_table_persists_its_signature(tmp_path: Path) -> None:
    """The 0-row path yields only hints plus the materialize marker.

    Whether dlt commits resource state for that shape is the design's one open
    risk. If this test fails, do NOT weaken it — apply the spec's contingency
    (attach the signature via `dlt.mark.with_hints`) and record the finding.
    """
    empty_signature = {"count": 0, "max_cursor": None}

    stored = _extract(
        f"sqlite:///{tmp_path / 'empty.db'}", rows=0, signature=empty_signature
    )

    assert stored == {"referrals": empty_signature}


def test_no_signature_writes_no_state(tmp_path: Path) -> None:
    """A None signature must not create a state key."""
    _seed(f"sqlite:///{tmp_path / 'none.db'}", rows=1)

    pipelines_dir = tempfile.mkdtemp(prefix="focus-nosig-")
    try:
        pipeline = dlt.pipeline(
            pipeline_name="focus_nosig_test",
            destination=bigquery(autodetect_schema=True),
            dataset_name="test",
            pipelines_dir=pipelines_dir,
        )
        pipeline.extract(
            build_focus_source(
                sql_database_credentials=ConnectionStringCredentials(
                    f"sqlite:///{tmp_path / 'none.db'}"
                ),
                tables=[ProbeTable(name="referrals", cursor_column=None)],
                signatures=None,
                db_schema=None,
            ),
            loader_file_format="parquet",
        )

        assert stored_signatures(pipeline, "focus") == {}
    finally:
        shutil.rmtree(pipelines_dir, ignore_errors=True)
