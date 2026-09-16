import json
import re

import pytest

# trunk-ignore(pyright/reportMissingImports): conftest.py puts docs/ on sys.path at runtime
from launch.build import Catalog, CatalogError, build, render

CONFIG = {
    "minimum_verified": 2,
    "groups": [
        {"id": "attendance", "name": "Attendance & behavior"},
        {"id": "academics", "name": "Academics & assessment"},
    ],
    "families": [],
    "promos": [{"label": "Guides", "blurb": "All", "url": "https://x.test"}],
}

TEMPLATE = "<html><script>const CATALOG = __CATALOG__;</script></html>"


def entry(**over):
    base = {
        "id": "t",
        "name": "T",
        "url": "https://x.test",
        "system": "tableau",
        "status": "verified",
        "group": "attendance",
        "description": "d",
        "audiences": ["ops"],
    }
    return {**base, **over}


def catalog(entries, config=None):
    return Catalog(entries=entries, config=config or CONFIG, template=TEMPLATE)


def payload(html):
    match = re.search(r"const CATALOG = (\{.*\});", html, re.S)
    # trunk-ignore(pyright/reportOptionalMemberAccess)
    return json.loads(match.group(1))


def test_below_threshold_renders_nothing():
    one = [entry(id="a", name="A")]
    assert render(catalog(one), one) is None


def test_at_threshold_renders_a_page():
    two = [entry(id="a", name="A"), entry(id="b", name="B")]
    assert render(catalog(two), two) is not None


def test_only_verified_entries_reach_the_payload():
    entries = [
        entry(id="a", name="A"),
        entry(id="b", name="B"),
        entry(id="c", name="C", status="needs-review"),
    ]
    verified = [e for e in entries if e["status"] == "verified"]
    got = payload(render(catalog(entries), verified))
    assert [t["id"] for t in got["tools"]] == ["a", "b"]


def test_a_closing_script_tag_cannot_escape_the_payload():
    entries = [
        entry(id="a", name="A", description="</script><img src=x onerror=alert(1)>"),
        entry(id="b", name="B"),
    ]
    html = render(catalog(entries), entries)
    assert "</script><img" not in html
    assert "\\u003c/script" in html
    assert payload(html)["tools"][0]["description"].startswith("</script>")


def test_the_limited_badge_needs_the_exact_value():
    entries = [
        entry(id="a", name="A", access="limited"),
        entry(id="b", name="B", description="limited access is mentioned here"),
    ]
    got = payload(render(catalog(entries), entries))
    by_id = {t["id"]: t for t in got["tools"]}
    assert by_id["a"]["limited"] is True
    assert by_id["b"]["limited"] is False


def test_family_members_carry_a_region_label_and_colour():
    config = {
        **CONFIG,
        "families": [
            {
                "id": "f",
                "name": "Fam",
                "description": "d",
                "group": "academics",
                "members": ["A", "B"],
            }
        ],
    }
    entries = [
        entry(id="a", name="A", regions=["camden"]),
        entry(id="b", name="B", regions=["miami"]),
    ]
    got = payload(render(catalog(entries, config), entries))
    labels = {t["id"]: t["regionLabel"] for t in got["tools"]}
    assert labels == {"a": "Camden", "b": "Miami"}
    assert all(t["family"]["id"] == "f" for t in got["tools"])


def test_unknown_system_falls_back_to_the_raw_value():
    entries = [entry(id="a", name="A", system="google-doc"), entry(id="b", name="B")]
    got = payload(render(catalog(entries), entries))
    assert got["tools"][0]["systemLabel"] == "Google Doc"


def test_a_missing_date_does_not_fail_the_build(tmp_path):
    # tmp_path is not a git repo, so _updated() must swallow the failure.
    (tmp_path / "links.yml").write_text(
        "- id: a\n  name: A\n  url: https://x.test\n  system: tableau\n"
        "  status: verified\n  group: attendance\n  description: d\n"
        "  audiences: [ops]\n"
        "- id: b\n  name: B\n  url: https://x.test\n  system: tableau\n"
        "  status: verified\n  group: attendance\n  description: d\n"
        "  audiences: [ops]\n"
    )
    (tmp_path / "groups.yml").write_text(
        "minimum_verified: 2\n"
        "groups:\n  - id: attendance\n    name: Attendance\n"
        "families: []\n"
        "promos:\n  - label: G\n    blurb: b\n    url: https://x.test\n"
    )
    (tmp_path / "template.html").write_text(TEMPLATE)

    html = build(tmp_path)

    assert html is not None
    assert payload(html)["meta"]["updated"] == ""


def test_build_raises_with_every_problem_listed(tmp_path):
    (tmp_path / "links.yml").write_text(
        "- id: BAD\n  name: X\n  url: http://x\n  system: notion\n  status: nope\n"
    )
    (tmp_path / "groups.yml").write_text("groups: []\nfamilies: []\npromos: []\n")
    (tmp_path / "template.html").write_text(TEMPLATE)

    with pytest.raises(CatalogError) as excinfo:
        build(tmp_path)

    assert len(excinfo.value.errors) >= 4
