# trunk-ignore-begin(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
from fakes import FakeSession
from publish_article import ZendeskHelpCenter, search_articles

# trunk-ignore-end(pyright/reportMissingImports)


def test_search_articles_clamps_limit_to_the_api_range(capsys):
    session = FakeSession(
        {("GET", "/help_center/articles/search.json"): (200, {"results": []})}
    )
    client = ZendeskHelpCenter("sub", "me@example.org", "tok", session=session)
    search_articles("x", limit=500, client=client)
    search_articles("x", limit=0, client=client)
    capsys.readouterr()
    assert [kw["params"]["per_page"] for _, _, kw in session.calls] == [100, 1]


def test_search_articles_hits_help_center_search_and_prints(capsys):
    session = FakeSession(
        {
            ("GET", "/help_center/articles/search.json"): (
                200,
                {
                    "results": [
                        {
                            "id": 1,
                            "title": "How to access Tableau",
                            "html_url": "https://sub.zendesk.com/hc/en-us/articles/1",
                            "section_id": 5,
                            "updated_at": "2026-09-29T00:00:00Z",
                        }
                    ]
                },
            )
        }
    )
    client = ZendeskHelpCenter("sub", "me@example.org", "tok", session=session)
    results = search_articles("tableau", limit=5, client=client)
    assert [r["id"] for r in results] == [1]
    assert session.calls[0][2]["params"] == {"query": "tableau", "per_page": 5}
    out = capsys.readouterr().out
    assert "How to access Tableau" in out and "articles/1" in out
