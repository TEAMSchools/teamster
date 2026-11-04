# trunk-ignore-begin(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
import pytest
import zendesk_tickets
from fakes import FakeSession
from zendesk_tickets import (
    TicketError,
    ZendeskTickets,
    draft_comment,
    draft_macro,
)

# trunk-ignore-end(pyright/reportMissingImports)

TICKET = {
    "id": 12,
    "subject": "Gradebook",
    "status": "open",
    "requester_id": 10,
    "assignee_id": None,
    "group_id": 21474460,
    "created_at": "2026-09-01T12:00:00Z",
    "updated_at": "2026-09-02T12:00:00Z",
    "custom_fields": [{"id": 20721852, "value": None}],
    "tags": ["existing"],
    "email_ccs": [],
}
USERS = [
    {"id": 10, "name": "Rae Requester"},
    {"id": 20, "name": "Ada Example", "email": "ada@example.org"},
]
CLOSE_OUT = 360047059914
ASSIGN_TECH = 37089224


def routes():
    ticket = TICKET
    return {
        ("GET", "/tickets/12.json"): (
            200,
            {
                "ticket": ticket,
                "users": USERS,
                "groups": [{"id": 21474460, "name": "Data"}],
            },
        ),
        ("GET", "/ticket_fields/20721852.json"): (
            200,
            {
                "ticket_field": {
                    "custom_field_options": [
                        {"name": "Data::PowerSchool", "value": "data_power_school"}
                    ]
                }
            },
        ),
        ("GET", "/groups.json"): (
            200,
            {
                "groups": [{"id": 21474460, "name": "Data", "deleted": False}],
                "meta": {"has_more": False},
            },
        ),
        ("GET", "/groups/21474460/memberships.json"): (
            200,
            {"group_memberships": [{"user_id": 20}], "meta": {"has_more": False}},
        ),
        ("GET", "/users/show_many.json"): (200, {"users": USERS[1:]}),
        ("GET", "/macros.json"): (
            200,
            {
                "macros": [
                    {"id": CLOSE_OUT, "title": "Data - Close Out Older Ticket"},
                    {"id": ASSIGN_TECH, "title": "Assign to Technology"},
                ],
                "meta": {"has_more": False},
            },
        ),
        ("GET", f"/tickets/12/macros/{ASSIGN_TECH}/apply.json"): (
            200,
            {
                "result": {
                    "ticket": {
                        "id": 12,
                        "status": "open",
                        "group_id": 20148286,
                        "custom_fields": [
                            {"id": 20721852, "value": None},
                            {"id": 20723572, "value": "room9"},
                        ],
                        "email_ccs": [{"user_id": 5, "action": "put"}],
                    }
                }
            },
        ),
        ("GET", f"/tickets/12/macros/{CLOSE_OUT}/apply.json"): (
            200,
            {
                "result": {
                    "ticket": {
                        "id": 12,
                        "url": "x",
                        "status": "solved",
                        "custom_fields": [{"id": 20721852, "value": None}],
                        "comment": {
                            "body": "Hi Rae - closing this out.",
                            "public": True,
                            "scoped_body": [],
                        },
                    }
                }
            },
        ),
    }


def make_client(r=None) -> tuple[ZendeskTickets, FakeSession]:
    session = FakeSession(r or routes())
    return ZendeskTickets("sub", "me@example.org", "tok", session=session), session


def internal_draft(client):
    return draft_comment(12, "note", public=False, runner="Ada", client=client)


def test_public_is_required_keyword():
    client, _ = make_client()
    with pytest.raises(TypeError):
        draft_comment(12, "hi", client=client)  # type: ignore[call-arg]


@pytest.mark.parametrize("value", [None, 0, 1, "no", "yes"])
def test_public_must_be_a_real_bool(value):
    client, session = make_client()
    with pytest.raises(TicketError) as info:
        draft_comment(12, "hi", public=value, runner="Ada", client=client)
    assert "True or False" in str(info.value)
    assert session.calls == []


def test_draft_macro_drops_unchanged_keys_and_refuses_assign_that_solves():
    r = routes()
    r[("GET", f"/tickets/12/macros/{ASSIGN_TECH}/apply.json")] = (
        200,
        {
            "result": {
                "ticket": {
                    "status": "open",
                    "group_id": 20148286,
                    "tags": ["existing"],
                    "custom_fields": [{"id": 20721852, "value": None}],
                    "email_ccs": [],
                }
            }
        },
    )
    client, _ = make_client(r)
    draft = draft_macro(12, "Assign to Technology", runner="Ada", client=client)
    assert draft.payload["ticket"] == {"group_id": 20148286}

    r[("GET", f"/tickets/12/macros/{ASSIGN_TECH}/apply.json")] = (
        200,
        {"result": {"ticket": {"status": "solved", "group_id": 20148286}}},
    )
    client, _ = make_client(r)
    with pytest.raises(TicketError) as info:
        draft_macro(12, "Assign to Technology", runner="Ada", client=client)
    assert "solved" in str(info.value)


def test_internal_draft_needs_runner_and_gets_signature(capsys):
    client, _ = make_client()
    with pytest.raises(TicketError):
        draft_comment(12, "note", public=False, client=client)
    draft = internal_draft(client)
    comment = draft.payload["ticket"]["comment"]
    assert comment["public"] is False
    assert comment["body"] == "note\n\nPosted via Claude by Ada"
    out = capsys.readouterr().out
    assert "INTERNAL" in out and "paste it into the ticket in Zendesk yourself" in out
    assert "draft file" not in out


def test_drafts_only_read_from_zendesk():
    client, session = make_client()
    draft_comment(
        12,
        "Hi Rae",
        public=True,
        status="pending",
        assignee="ada",
        category="PowerSchool",
        client=client,
    )
    draft_macro(12, "Data - Close Out Older Ticket", runner="Ada", client=client)
    assert session.calls
    assert {method for method, _, _ in session.calls} == {"GET"}
    assert not hasattr(zendesk_tickets, "apply")
    assert not hasattr(ZendeskTickets, "update_ticket")


def test_public_draft_has_no_signature_and_resolves_fields(capsys):
    client, _ = make_client()
    draft = draft_comment(
        12,
        "Hi Rae",
        public=True,
        status="pending",
        assignee="ada",
        category="PowerSchool",
        client=client,
    )
    ticket = draft.payload["ticket"]
    assert ticket["comment"] == {"body": "Hi Rae", "public": True}
    assert ticket["status"] == "pending"
    assert ticket["assignee_id"] == 20
    assert ticket["custom_fields"] == [{"id": 20721852, "value": "data_power_school"}]
    out = capsys.readouterr().out
    assert "PUBLIC" in out
    assert "status: open -> pending" in out
    assert "assignee:  -> Ada Example" in out
    assert "category:  -> Data::PowerSchool" in out


def test_draft_macro_keeps_writable_keys_and_marks_public(capsys):
    client, _ = make_client()
    draft = draft_macro(
        12,
        "Data - Close Out Older Ticket",
        runner="Ada",
        client=client,
    )
    ticket = draft.payload["ticket"]
    assert set(ticket) == {"status", "comment"}  # unchanged custom_fields dropped
    assert ticket["comment"]["public"] is True
    assert "Posted via Claude" not in ticket["comment"]["body"]
    out = capsys.readouterr().out
    assert (
        "PUBLIC" in out
        and "status: open -> solved" in out
        and "cannot post to Zendesk" in out
    )


def test_draft_macro_sends_html_comment_as_html_body(capsys):
    r = routes()
    r[("GET", f"/tickets/12/macros/{CLOSE_OUT}/apply.json")] = (
        200,
        {
            "result": {
                "ticket": {
                    "status": "solved",
                    "comment": {
                        "body": "<p>Hi Rae - </p><p>closing this out.</p>",
                        "public": False,
                    },
                }
            }
        },
    )
    client, _ = make_client(r)
    draft = draft_macro(
        12,
        "Data - Close Out Older Ticket",
        runner="Ada",
        client=client,
    )
    comment = draft.payload["ticket"]["comment"]
    assert "body" not in comment
    assert comment["html_body"] == (
        "<p>Hi Rae - </p><p>closing this out.</p><p>Posted via Claude by Ada</p>"
    )
    out = capsys.readouterr().out
    assert "<p>" not in out
    assert "Hi Rae -" in out and "closing this out." in out


def test_draft_macro_without_comment_shows_every_field_change(capsys):
    client, _ = make_client()
    draft = draft_macro(12, "Assign to Technology", runner="Ada", client=client)
    ticket = draft.payload["ticket"]
    assert "comment" not in ticket
    out = capsys.readouterr().out
    assert "comment: none" in out
    assert "INTERNAL" not in out
    assert "group_id: 21474460 -> 20148286" in out
    assert "custom_field 20723572:  -> room9" in out
    assert "email_ccs:" in out


def test_assignee_on_ungrouped_ticket_is_a_plain_refusal():
    r = routes()
    r[("GET", "/tickets/12.json")] = (
        200,
        {"ticket": TICKET | {"group_id": None}, "users": USERS, "groups": []},
    )
    client, session = make_client(r)
    with pytest.raises(TicketError) as info:
        draft_comment(
            12,
            "hi",
            public=False,
            runner="Ada",
            assignee="ada",
            client=client,
        )
    assert "no group" in str(info.value)
    assert all("/groups/None/" not in p for p in session.paths("GET"))


def test_solving_draft_says_it_reaches_the_requester(capsys):
    client, _ = make_client()
    draft_comment(
        12,
        "done",
        public=False,
        runner="Ada",
        status="solved",
        client=client,
    )
    out = capsys.readouterr().out
    assert "reaches the requester" in out


def test_draft_macro_refuses_outside_allowlist():
    client, _ = make_client()
    with pytest.raises(TicketError):
        draft_macro(12, "Data - Amplify", runner="Ada", client=client)
