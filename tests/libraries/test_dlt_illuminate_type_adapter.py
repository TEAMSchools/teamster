"""Unit tests for the Illuminate dlt numeric type adapter.

Before SQLAlchemy 2.1, `Float` subclassed `Numeric` and reflected
`precision=None`, so `unbounded_numeric_adapter` widened every Postgres `real` /
`double precision` column to `Numeric(38, 18)` and it landed as BIGNUMERIC.
SQLAlchemy 2.1 split the two, the widening stopped, and the BigQuery load failed
with "changed type from BIGNUMERIC to FLOAT". Floats now land as FLOAT64 on
purpose; these tests pin that regardless of the installed SQLAlchemy.
"""

import pytest
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, NUMERIC, REAL
from sqlalchemy.sql import sqltypes

from teamster.libraries.dlt.illuminate.assets import unbounded_numeric_adapter


def test_unbounded_numeric_is_widened():
    widened = unbounded_numeric_adapter(NUMERIC())

    assert isinstance(widened, sqltypes.Numeric)
    assert (widened.precision, widened.scale) == (38, 18)


def test_bounded_numeric_passes_through():
    bounded = NUMERIC(precision=10, scale=2)

    assert unbounded_numeric_adapter(bounded) is bounded


@pytest.mark.parametrize("col_type", [REAL(), DOUBLE_PRECISION()])
def test_floats_pass_through(col_type):
    assert unbounded_numeric_adapter(col_type) is col_type
