# trunk-ignore(pyright/reportMissingImports): conftest.py puts docs/ on sys.path at runtime
from launch.build import Catalog, select


def catalog(*statuses) -> Catalog:
    return Catalog(
        entries=[
            {"id": f"t{i}", "name": f"T{i}", "status": s}
            for i, s in enumerate(statuses)
        ],
        config={},
        template="",
    )


def test_select_keeps_only_verified():
    got = select(catalog("verified", "needs-review", "verified"))
    assert [e["id"] for e in got] == ["t0", "t2"]


def test_select_preserves_catalog_order():
    got = select(catalog("verified", "verified", "verified"))
    assert [e["id"] for e in got] == ["t0", "t1", "t2"]


def test_select_returns_empty_when_nothing_is_verified():
    assert select(catalog("needs-review", "needs-review")) == []
