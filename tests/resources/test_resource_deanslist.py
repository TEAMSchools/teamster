import logging
import pathlib

import pytest

from teamster.libraries.deanslist.resources import (
    DeansListResource,
    load_deanslist_config,
)


def test_load_deanslist_config(tmp_path: pathlib.Path):
    (tmp_path / "subdomain").write_text("kippnj\n")
    (tmp_path / "121").write_text("key-121\n")
    (tmp_path / "122").write_text("key-122")
    # projected-secret volumes stage data behind dot-prefixed entries
    (tmp_path / "..data").mkdir()
    (tmp_path / ".hidden").write_text("ignore-me")

    subdomain, api_key_map = load_deanslist_config(tmp_path)

    assert subdomain == "kippnj"
    assert api_key_map == {121: "key-121", 122: "key-122"}


def test_request_missing_school_key_raises_named_error():
    resource = DeansListResource(api_key_dir="/etc/deanslist")
    object.__setattr__(resource, "_api_key_map", {121: "key-121"})
    object.__setattr__(resource, "_log", logging.getLogger("test"))

    # school_id 999 has no key file synced — the guard must raise before any
    # network call, naming the school id and the mount
    with pytest.raises(KeyError, match="No DeansList API key for school_id 999"):
        resource._request(method="GET", url="https://x/api", school_id=999, params={})
