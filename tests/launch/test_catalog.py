"""The real catalog must always be valid. This is the test that protects main.

The others prove the rules work; this one proves the data obeys them.
"""

# trunk-ignore(pyright/reportMissingImports): conftest.py puts docs/ on sys.path at runtime
from launch.build import load, select, validate


def test_the_real_catalog_is_valid():
    catalog = load()
    errors = validate(catalog, select(catalog))
    assert errors == [], "\n".join(errors)


def test_the_real_catalog_is_not_accidentally_empty():
    # Guards against a path regression silently passing the test above.
    assert len(load().entries) > 30


def test_every_family_member_resolves():
    catalog = load()
    names = {e["name"] for e in catalog.entries}
    for family in catalog.config["families"]:
        for member in family["members"]:
            assert member in names, f"{family['id']} names missing {member!r}"
