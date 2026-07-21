"""Unit tests for the dlt extract-worker concurrency cap (DPY-4011 fix).

Covers `_resolve_extract_workers`: a per-run `dlt_extract_workers` tag
overrides the factory's `max_extract_workers` param, which overrides dlt's
default (unset EXTRACT__WORKERS -> dlt's default of 5).
"""

from teamster.libraries.dlt.powerschool.assets import _resolve_extract_workers


def test_resolve_extract_workers_no_tag_no_param_leaves_default():
    assert _resolve_extract_workers(None, None) is None


def test_resolve_extract_workers_no_tag_uses_param():
    assert _resolve_extract_workers(None, 1) == 1


def test_resolve_extract_workers_tag_overrides_param():
    assert _resolve_extract_workers("3", 1) == 3


def test_resolve_extract_workers_tag_no_param():
    assert _resolve_extract_workers("2", None) == 2
