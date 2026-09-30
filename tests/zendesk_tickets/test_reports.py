# trunk-ignore-begin(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
from fakes import FakeSession
from zendesk_tickets import (
    ZendeskTickets,
    format_rows,
    keywords,
    queue,
    research,
    search,
    thread,
)

# trunk-ignore-end(pyright/reportMissingImports)

USERS = [
    {
        "id": 10,
        "name": "Rae Requester",
        "email": "rae@example.org",
        "organization_id": None,
    },
    {"id": 20, "name": "Ada Example", "email": "ada@example.org"},
]
TICKET = {
    "id": 12,
    "subject": "Cannot log in to PowerSchool gradebook",
    "status": "open",
    "requester_id": 10,
    "assignee_id": 20,
    "group_id": 21474460,
    "created_at": "2026-09-01T12:00:00Z",
    "updated_at": "2026-09-02T12:00:00Z",
    "custom_fields": [
        {"id": 20721852, "value": "data_power_school"},
        {"id": 20723572, "value": None},
    ],
}
COMMENTS = [
    {
        "id": 1,
        "author_id": 10,
        "public": True,
        "created_at": "2026-09-01T12:00:00Z",
        "plain_body": "I cannot log in.",
        "attachments": [{"file_name": "shot.png"}],
    },
    {
        "id": 2,
        "author_id": 20,
        "public": False,
        "created_at": "2026-09-02T12:00:00Z",
        "plain_body": "Checking SSO.",
        "attachments": [],
    },
]


def _ticket(id_, status, subject, created, **extra):
    return {
        "id": id_,
        "result_type": "ticket",
        "status": status,
        "subject": subject,
        "created_at": created,
    } | extra


def search_handler(kwargs):
    query = kwargs["params"]["query"]
    if "requester:10" in query:
        return 200, {
            "results": [_ticket(7, "solved", "Old one", "2026-08-01T00:00:00Z")]
        }
    if "custom_field_20721852:data_power_school" in query:
        return 200, {
            "results": [
                _ticket(12, "open", "self", "2026-09-01T00:00:00Z"),
                _ticket(8, "solved", "Gradebook access", "2026-07-01T00:00:00Z"),
            ]
        }
    if "status<solved" in query:
        return 200, {
            "results": [
                _ticket(
                    3,
                    "open",
                    "B",
                    "2026-09-20T00:00:00Z",
                    requester_id=10,
                    assignee_id=None,
                    custom_fields=[{"id": 20721852, "value": "data_illuminate"}],
                ),
                {"id": 4, "result_type": "user", "name": "noise"},
            ]
        }
    return 200, {
        "results": [
            _ticket(
                9, "pending", "PowerSchool gradebook locked", "2026-06-01T00:00:00Z"
            )
        ]
    }


ROUTES = {
    ("GET", "/tickets/12.json"): (
        200,
        {
            "ticket": TICKET,
            "users": USERS,
            "groups": [{"id": 21474460, "name": "Data"}],
        },
    ),
    ("GET", "/tickets/12/comments.json"): (
        200,
        {"comments": COMMENTS, "users": USERS, "meta": {"has_more": False}},
    ),
    ("GET", "/users/10.json"): (200, {"user": USERS[0]}),
    ("GET", "/search.json"): search_handler,
    ("GET", "/ticket_fields/20721852.json"): (
        200,
        {
            "ticket_field": {
                "custom_field_options": [
                    {"name": "Data::PowerSchool", "value": "data_power_school"},
                    {"name": "Data::Illuminate", "value": "data_illuminate"},
                ]
            }
        },
    ),
    ("GET", "/groups.json"): (
        200,
        {
            "groups": [
                {"id": 21474460, "name": "Data", "deleted": False},
                {"id": 31319068, "name": "Teaching & Learning", "deleted": False},
            ],
            "meta": {"has_more": False},
        },
    ),
    ("GET", "/users/show_many.json"): (200, {"users": USERS}),
}


def make_client() -> tuple[ZendeskTickets, FakeSession]:
    session = FakeSession(ROUTES)
    return ZendeskTickets("sub", "me@example.org", "tok", session=session), session


def _last_search_params(session):
    return [kw for _, p, kw in session.calls if p == "/search.json"][-1]["params"]


def test_keywords_strip_stopwords_and_cap_at_six():
    assert keywords("Cannot log in to the PowerSchool gradebook for my class") == [
        "cannot",
        "log",
        "powerschool",
        "gradebook",
        "class",
    ]
    assert len(keywords("aa bb cc dd ee ff gg hh")) <= 6


def test_format_rows_is_fixed_width_with_header():
    text = format_rows(
        [{"id": 1, "subject": "x"}, {"id": 22, "subject": "yy"}], ["id", "subject"]
    )
    lines = text.splitlines()
    assert lines[0].startswith("id")
    assert lines[1].startswith("1 ")
    assert lines[2].startswith("22")


def test_research_prints_header_thread_history_and_similar(capsys):
    client, _ = make_client()
    result = research(12, client=client)
    out = capsys.readouterr().out
    assert "#12" in out and "Cannot log in to PowerSchool gradebook" in out
    assert "Data::PowerSchool" in out
    assert "Ada Example" in out and "Rae Requester" in out
    assert "PUBLIC" in out and "INTERNAL" in out
    assert "shot.png" in out
    assert "Requester history" in out and "Old one" in out
    assert "Similar tickets" in out
    assert "Gradebook access" in out and "PowerSchool gradebook locked" in out
    assert [t["id"] for t in result["similar_by_category"]] == [8]
    assert result["organization"] is None


def test_thread_returns_comments(capsys):
    client, _ = make_client()
    comments = thread(12, client=client)
    assert [c["id"] for c in comments] == [1, 2]
    assert "Checking SSO." in capsys.readouterr().out


def test_search_prepends_type_and_group_terms(capsys):
    client, session = make_client()
    search("gradebook", groups=["Data"], client=client)
    query = _last_search_params(session)["query"]
    assert query.startswith("type:ticket ")
    assert "group_id:21474460" in query
    assert "gradebook" in query


def test_queue_filters_to_tickets_and_shows_category_names(capsys):
    client, session = make_client()
    rows = queue(client=client)
    params = _last_search_params(session)
    assert "status<solved" in params["query"]
    assert "group_id:21474460" in params["query"]
    assert "group_id:31319068" in params["query"]
    assert params["sort_order"] == "asc"
    assert [r["id"] for r in rows] == [3]
    out = capsys.readouterr().out
    assert "Data::Illuminate" in out
    assert "noise" not in out
