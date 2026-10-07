# trunk-ignore-begin(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
import pytest
from fakes import FakeSession
from zendesk_tickets import TicketError, ZendeskTickets, client_from_environment

# trunk-ignore-end(pyright/reportMissingImports)


def make_client(routes) -> tuple[ZendeskTickets, FakeSession]:
    session = FakeSession(routes)
    return ZendeskTickets("sub", "me@example.org", "tok", session=session), session


def test_auth_is_email_slash_token_basic_auth():
    client, session = make_client({})
    assert session.auth == ("me@example.org/token", "tok")
    assert client.base == "https://sub.zendesk.com/api/v2"
    assert client.ticket_url(12) == "https://sub.zendesk.com/agent/tickets/12"


def test_get_ticket_side_loads_users_and_groups():
    client, session = make_client(
        {
            ("GET", "/tickets/12.json"): (
                200,
                {"ticket": {"id": 12}, "users": [{"id": 1}], "groups": [{"id": 2}]},
            )
        }
    )
    result = client.get_ticket(12)
    assert result["ticket"] == {"id": 12}
    assert result["users"] == [{"id": 1}]
    _, _, kwargs = session.calls[0]
    assert kwargs["params"] == {"include": "users,groups"}


def test_comments_returns_comments_and_side_loaded_users():
    client, session = make_client(
        {
            ("GET", "/tickets/12/comments.json"): (
                200,
                {
                    "comments": [{"id": 5}],
                    "users": [{"id": 1}],
                    "meta": {"has_more": False},
                },
            )
        }
    )
    comments, users = client.comments(12)
    assert comments == [{"id": 5}]
    assert users == [{"id": 1}]
    _, _, kwargs = session.calls[0]
    assert kwargs["params"]["include"] == "users"


def test_search_unwraps_results_and_passes_sort():
    client, session = make_client(
        {
            ("GET", "/search.json"): (
                200,
                {"results": [{"id": 1, "result_type": "ticket"}]},
            )
        }
    )
    assert client.search("type:ticket foo") == [{"id": 1, "result_type": "ticket"}]
    _, _, kwargs = session.calls[0]
    assert kwargs["params"] == {
        "query": "type:ticket foo",
        "sort_by": "created_at",
        "sort_order": "desc",
        "per_page": 100,
        "page": 1,
    }


def _search_pages(kw):
    page = kw["params"].get("page", 1)
    if page == 1:
        return 200, {
            "results": [{"id": 1, "result_type": "ticket"}],
            "next_page": "https://sub.zendesk.com/api/v2/search.json?page=2&query=x",
            "count": 2,
        }
    return 200, {
        "results": [{"id": 2, "result_type": "ticket"}],
        "next_page": None,
        "count": 2,
    }


def test_search_follows_next_page_until_exhausted():
    client, session = make_client({("GET", "/search.json"): _search_pages})
    assert client.search("type:ticket x") == [
        {"id": 1, "result_type": "ticket"},
        {"id": 2, "result_type": "ticket"},
    ]
    assert [kw["params"]["page"] for _, _, kw in session.calls] == [1, 2]


def test_search_stops_at_max_results_and_shrinks_the_page():
    client, session = make_client({("GET", "/search.json"): _search_pages})
    assert client.search("type:ticket x", max_results=1) == [
        {"id": 1, "result_type": "ticket"}
    ]
    assert len(session.calls) == 1
    assert session.calls[0][2]["params"]["per_page"] == 1


def _macro_pages(kw):
    if kw["params"].get("page[after]") == "abc":
        return 200, {
            "macros": [{"id": 2}],
            "meta": {"has_more": False},
            "links": {"next": None},
        }
    return 200, {
        "macros": [{"id": 1}],
        "meta": {"has_more": True, "after_cursor": "abc"},
        "links": {"next": "https://sub.zendesk.com/api/v2/macros.json?page[after]=abc"},
    }


def test_list_all_follows_cursor_pages():
    client, session = make_client({("GET", "/macros.json"): _macro_pages})
    assert client.macros() == [{"id": 1}, {"id": 2}]
    assert len(session.calls) == 2
    assert session.calls[0][2]["params"]["active"] == "true"


def test_users_show_many_joins_ids():
    client, session = make_client(
        {("GET", "/users/show_many.json"): (200, {"users": [{"id": 1}, {"id": 2}]})}
    )
    assert client.users_show_many([1, 2]) == [{"id": 1}, {"id": 2}]
    assert session.calls[0][2]["params"] == {"ids": "1,2"}


def test_users_show_many_chunks_by_100():
    client, session = make_client(
        {
            ("GET", "/users/show_many.json"): lambda kw: (
                200,
                {"users": [{"id": int(i)} for i in kw["params"]["ids"].split(",")]},
            )
        }
    )
    users = client.users_show_many(list(range(1, 251)))
    assert [u["id"] for u in users] == list(range(1, 251))
    sizes = [len(kw["params"]["ids"].split(",")) for _, _, kw in session.calls]
    assert sizes == [100, 100, 50]


def test_macro_preview_unwraps_result_ticket():
    client, _ = make_client(
        {
            ("GET", "/tickets/12/macros/9/apply.json"): (
                200,
                {"result": {"ticket": {"status": "solved", "comment": {"body": "hi"}}}},
            )
        }
    )
    assert client.macro_preview(12, 9) == {
        "status": "solved",
        "comment": {"body": "hi"},
    }


def test_http_error_becomes_ticket_error_naming_the_call():
    client, _ = make_client(
        {("GET", "/tickets/404.json"): (404, {"error": "RecordNotFound"})}
    )
    with pytest.raises(TicketError) as info:
        client.get_ticket(404)
    assert "GET /tickets/404.json returned 404" in str(info.value)


def test_client_from_environment_names_missing_variable(monkeypatch):
    for name in ("ZENDESK_SUBDOMAIN", "ZENDESK_EMAIL", "ZENDESK_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(TicketError) as info:
        client_from_environment()
    assert "ZENDESK_SUBDOMAIN is not set" in str(info.value)
    assert "tests/test_zz_" in str(info.value)


def test_client_from_environment_builds_client(monkeypatch):
    monkeypatch.setenv("ZENDESK_SUBDOMAIN", "sub")
    monkeypatch.setenv("ZENDESK_EMAIL", "me@example.org")
    monkeypatch.setenv("ZENDESK_TOKEN", "tok")
    client = client_from_environment()
    assert client.base == "https://sub.zendesk.com/api/v2"
