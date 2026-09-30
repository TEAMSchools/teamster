import json

# trunk-ignore-begin(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
import pytest
import zendesk_tickets
from fakes import FakeSession
from zendesk_tickets import (
    TicketError,
    ZendeskTickets,
    apply,
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


def routes(updated_at="2026-09-02T12:00:00Z", put=None):
    ticket = TICKET | {"updated_at": updated_at}
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
        ("GET", "/users/me.json"): (200, {"user": {"id": 99, "name": "Tok Owner"}}),
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
        ("PUT", "/tickets/12.json"): put
        or (200, {"ticket": TICKET | {"status": "pending"}}),
    }


def make_client(r=None) -> tuple[ZendeskTickets, FakeSession]:
    session = FakeSession(r or routes())
    return ZendeskTickets("sub", "me@example.org", "tok", session=session), session


def internal_draft(client, tmp_path):
    return draft_comment(
        12, "note", public=False, drafts_dir=tmp_path, runner="Ada", client=client
    )


def separate_process():
    """Tests draft and apply in one process; a real session runs two pytest runs."""
    zendesk_tickets.reset_process_guard()


def test_public_is_required_keyword():
    client, _ = make_client()
    with pytest.raises(TypeError):
        draft_comment(12, "hi", drafts_dir="x", client=client)  # type: ignore[call-arg]


@pytest.mark.parametrize("value", [None, 0, 1, "no", "yes"])
def test_public_must_be_a_real_bool(tmp_path, value):
    client, session = make_client()
    with pytest.raises(TicketError) as info:
        draft_comment(
            12, "hi", public=value, drafts_dir=tmp_path, runner="Ada", client=client
        )
    assert "True or False" in str(info.value)
    assert list(tmp_path.iterdir()) == []
    assert session.paths("PUT") == []


def test_draft_refuses_a_folder_inside_a_checkout(tmp_path):
    (tmp_path / ".git").mkdir()
    client, _ = make_client()
    with pytest.raises(TicketError) as info:
        draft_comment(
            12,
            "hi",
            public=False,
            drafts_dir=tmp_path / "drafts",
            runner="Ada",
            client=client,
        )
    assert "scratchpad" in str(info.value)
    assert not (tmp_path / "drafts").exists()


def test_apply_refuses_in_the_same_process_as_a_draft(tmp_path):
    client, session = make_client()
    draft = internal_draft(client, tmp_path)
    with pytest.raises(TicketError) as info:
        apply(draft.path, client=client)
    assert "same" in str(info.value)
    assert session.paths("PUT") == []
    assert draft.path.exists()


def test_apply_refuses_a_hand_edited_draft(tmp_path):
    client, session = make_client()
    draft = internal_draft(client, tmp_path)
    edited = json.loads(draft.path.read_text())
    edited["payload"]["ticket"]["comment"]["body"] = "edited by hand"
    draft.path.write_text(json.dumps(edited))
    separate_process()
    with pytest.raises(TicketError) as info:
        apply(draft.path, client=client)
    assert "does not match" in str(info.value)
    assert session.paths("PUT") == []
    assert draft.path.exists()


def test_apply_refuses_keys_outside_the_allowlist_and_bad_files(tmp_path):
    client, session = make_client()
    draft = internal_draft(client, tmp_path)
    saved = json.loads(draft.path.read_text())
    saved["payload"]["ticket"]["requester_id"] = 12345
    saved["payload_sha256"] = zendesk_tickets.payload_sha256(saved["payload"])
    draft.path.write_text(json.dumps(saved))
    separate_process()
    with pytest.raises(TicketError) as info:
        apply(draft.path, client=client)
    assert "requester_id" in str(info.value)

    saved = json.loads(draft.path.read_text())
    del saved["payload"]["ticket"]["requester_id"]
    saved["updated_at"] = None
    saved["payload_sha256"] = zendesk_tickets.payload_sha256(saved["payload"])
    draft.path.write_text(json.dumps(saved))
    with pytest.raises(TicketError):
        apply(draft.path, client=client)

    with pytest.raises(TicketError):
        apply(tmp_path / "missing.json", client=client)
    (tmp_path / "bad.json").write_text("{not json")
    with pytest.raises(TicketError):
        apply(tmp_path / "bad.json", client=client)
    assert session.paths("PUT") == []


def test_draft_macro_drops_unchanged_keys_and_refuses_assign_that_solves(tmp_path):
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
    draft = draft_macro(
        12, "Assign to Technology", drafts_dir=tmp_path, runner="Ada", client=client
    )
    assert draft.payload["ticket"] == {"group_id": 20148286}

    r[("GET", f"/tickets/12/macros/{ASSIGN_TECH}/apply.json")] = (
        200,
        {"result": {"ticket": {"status": "solved", "group_id": 20148286}}},
    )
    client, _ = make_client(r)
    with pytest.raises(TicketError) as info:
        draft_macro(
            12, "Assign to Technology", drafts_dir=tmp_path, runner="Ada", client=client
        )
    assert "solved" in str(info.value)


def test_internal_draft_needs_runner_and_gets_signature(tmp_path, capsys):
    client, session = make_client()
    with pytest.raises(TicketError):
        draft_comment(12, "note", public=False, drafts_dir=tmp_path, client=client)
    draft = internal_draft(client, tmp_path)
    comment = draft.payload["ticket"]["comment"]
    assert comment["public"] is False
    assert comment["body"] == "note\n\nPosted via Claude by Ada"
    assert session.paths("PUT") == []
    out = capsys.readouterr().out
    assert (
        "INTERNAL" in out and "posts as Tok Owner" in out and "not recommended" in out
    )
    saved = json.loads(draft.path.read_text())
    assert saved["payload"] == draft.payload
    assert saved["updated_at"] == "2026-09-02T12:00:00Z"


def test_public_draft_has_no_signature_and_resolves_fields(tmp_path, capsys):
    client, _ = make_client()
    draft = draft_comment(
        12,
        "Hi Rae",
        public=True,
        drafts_dir=tmp_path,
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


def test_draft_macro_keeps_writable_keys_and_marks_public(tmp_path, capsys):
    client, _ = make_client()
    draft = draft_macro(
        12,
        "Data - Close Out Older Ticket",
        drafts_dir=tmp_path,
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
        and "posts as Tok Owner" in out
        and "not recommended" in out
    )


def test_draft_macro_sends_html_comment_as_html_body(tmp_path, capsys):
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
        drafts_dir=tmp_path,
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


def test_draft_macro_without_comment_shows_every_field_change(tmp_path, capsys):
    client, _ = make_client()
    draft = draft_macro(
        12, "Assign to Technology", drafts_dir=tmp_path, runner="Ada", client=client
    )
    ticket = draft.payload["ticket"]
    assert "comment" not in ticket
    out = capsys.readouterr().out
    assert "comment: none" in out
    assert "INTERNAL" not in out
    assert "group_id: 21474460 -> 20148286" in out
    assert "custom_field 20723572:  -> room9" in out
    assert "email_ccs:" in out


def test_draft_macro_refuses_outside_allowlist(tmp_path):
    client, _ = make_client()
    with pytest.raises(TicketError):
        draft_macro(
            12, "Data - Amplify", drafts_dir=tmp_path, runner="Ada", client=client
        )


def test_apply_puts_stored_payload_with_safe_update_and_deletes_file(tmp_path, capsys):
    client, session = make_client()
    draft = internal_draft(client, tmp_path)
    separate_process()
    url = apply(draft.path, client=client)
    assert url == "https://sub.zendesk.com/agent/tickets/12"
    put = [kw for m, _, kw in session.calls if m == "PUT"][0]["json"]
    assert put["ticket"]["comment"] == draft.payload["ticket"]["comment"]
    assert put["ticket"]["safe_update"] is True
    assert put["ticket"]["updated_stamp"] == "2026-09-02T12:00:00Z"
    assert not draft.path.exists()
    assert url in capsys.readouterr().out


def test_apply_refuses_when_ticket_moved(tmp_path):
    client, _ = make_client()
    draft = internal_draft(client, tmp_path)
    moved, session = make_client(routes(updated_at="2026-09-03T09:00:00Z"))
    separate_process()
    with pytest.raises(TicketError) as info:
        apply(draft.path, client=moved)
    message = str(info.value)
    assert "2026-09-02T12:00:00Z" in message and "2026-09-03T09:00:00Z" in message
    assert session.paths("PUT") == []
    assert draft.path.exists()


def test_apply_surfaces_put_error_and_keeps_file(tmp_path):
    client, _ = make_client(routes(put=(422, {"error": "RecordInvalid"})))
    draft = internal_draft(client, tmp_path)
    separate_process()
    with pytest.raises(TicketError) as info:
        apply(draft.path, client=client)
    assert "422" in str(info.value)
    assert draft.path.exists()
