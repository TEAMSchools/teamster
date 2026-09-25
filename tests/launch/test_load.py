# trunk-ignore(pyright/reportMissingImports): conftest.py puts docs/ on sys.path at runtime
from launch.build import Catalog, load


def test_load_reads_the_three_sources(tmp_path):
    (tmp_path / "links.yml").write_text("- id: a\n  name: A\n")
    (tmp_path / "groups.yml").write_text("groups: []\nfamilies: []\npromos: []\n")
    (tmp_path / "template.html").write_text("<p>__CATALOG__</p>")

    catalog = load(tmp_path)

    assert isinstance(catalog, Catalog)
    assert catalog.entries == [{"id": "a", "name": "A"}]
    assert catalog.config["groups"] == []
    assert "__CATALOG__" in catalog.template


def test_load_defaults_to_the_real_catalog():
    catalog = load()
    assert len(catalog.entries) > 30
