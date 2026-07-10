import pathlib

from teamster.libraries.deanslist.resources import load_deanslist_config


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
