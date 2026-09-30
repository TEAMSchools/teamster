# trunk-ignore-begin(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
import pytest
from fakes import FakeSession
from zendesk_tickets import Catalog, TicketError, ZendeskTickets, macro_allowed

# trunk-ignore-end(pyright/reportMissingImports)

OPTIONS = [
    {"name": "Data::PowerSchool", "value": "data_power_school"},
    {
        "name": "Technology::System::PowerSchool",
        "value": "technology__system__powerschool",
    },
    {"name": "Data::Illuminate", "value": "data_illuminate"},
    {"name": "Teaching & Learning::Amplify", "value": "teaching___learning__amplify"},
]

ROUTES = {
    ("GET", "/ticket_fields/20721852.json"): (
        200,
        {"ticket_field": {"id": 20721852, "custom_field_options": OPTIONS}},
    ),
    ("GET", "/groups.json"): (
        200,
        {
            "groups": [
                {"id": 21474460, "name": "Data", "deleted": False},
                {"id": 31319068, "name": "Teaching & Learning", "deleted": False},
                {"id": 99, "name": "Old Data", "deleted": True},
            ],
            "meta": {"has_more": False},
        },
    ),
    ("GET", "/groups/21474460/memberships.json"): (
        200,
        {
            "group_memberships": [{"user_id": 1}, {"user_id": 2}],
            "meta": {"has_more": False},
        },
    ),
    ("GET", "/users/show_many.json"): (
        200,
        {
            "users": [
                {"id": 1, "name": "Ada Example", "email": "ada@example.org"},
                {"id": 2, "name": "Brook Sample", "email": "brook@example.org"},
            ]
        },
    ),
    ("GET", "/macros.json"): (
        200,
        {
            "macros": [
                {"id": 360047059914, "title": "Data - Close Out Older Ticket"},
                {"id": 137607547, "title": "Assign to Teaching & Learning"},
                {"id": 42793294718487, "title": "Data - Amplify"},
            ],
            "meta": {"has_more": False},
        },
    ),
}


def make_catalog() -> tuple[Catalog, FakeSession]:
    session = FakeSession(ROUTES)
    client = ZendeskTickets("sub", "me@example.org", "tok", session=session)
    return Catalog(client), session


def test_category_options_fetched_once():
    catalog, session = make_catalog()
    catalog.category_options()
    catalog.category_options()
    assert session.paths("GET") == ["/ticket_fields/20721852.json"]


def test_resolve_category_full_name_case_insensitive():
    catalog, _ = make_catalog()
    assert catalog.resolve_category("data::illuminate")["value"] == "data_illuminate"


def test_resolve_category_last_segment_when_unique():
    catalog, _ = make_catalog()
    assert (
        catalog.resolve_category("Amplify")["value"] == "teaching___learning__amplify"
    )


def test_resolve_category_ambiguous_lists_candidates():
    catalog, _ = make_catalog()
    with pytest.raises(TicketError) as info:
        catalog.resolve_category("PowerSchool")
    message = str(info.value)
    assert "Data::PowerSchool" in message
    assert "Technology::System::PowerSchool" in message


def test_resolve_category_missing_lists_closest():
    catalog, _ = make_catalog()
    with pytest.raises(TicketError) as info:
        catalog.resolve_category("Illumnate")
    assert "Data::Illuminate" in str(info.value)


def test_category_name_maps_tag_back_and_handles_none():
    catalog, _ = make_catalog()
    assert catalog.category_name("data_power_school") == "Data::PowerSchool"
    assert catalog.category_name(None) == ""
    assert catalog.category_name("unknown_tag") == "unknown_tag"


def test_resolve_group_exact_title_skips_deleted():
    catalog, _ = make_catalog()
    assert catalog.resolve_group("Data")["id"] == 21474460
    with pytest.raises(TicketError):
        catalog.resolve_group("Old Data")


def test_resolve_assignee_by_first_name_full_name_or_email():
    catalog, _ = make_catalog()
    assert catalog.resolve_assignee("ada", 21474460)["id"] == 1
    assert catalog.resolve_assignee("Brook Sample", 21474460)["id"] == 2
    assert catalog.resolve_assignee("brook@example.org", 21474460)["id"] == 2


def test_resolve_assignee_unknown_lists_members():
    catalog, _ = make_catalog()
    with pytest.raises(TicketError) as info:
        catalog.resolve_assignee("Zed", 21474460)
    assert "Ada Example" in str(info.value)


def test_macro_allowlist():
    assert macro_allowed("Data - Close Out Older Ticket")
    assert macro_allowed("Assign to Teaching & Learning")
    assert macro_allowed("Data - Assign to Special Education")
    assert macro_allowed("Data - Re-Assign to HR - Manager Assignment")
    assert not macro_allowed("Data - Amplify")
    assert not macro_allowed("Data - Zoom - Assign to Technology")


def test_resolve_macro_refuses_outside_allowlist():
    catalog, _ = make_catalog()
    assert catalog.resolve_macro("Data - Close Out Older Ticket")["id"] == 360047059914
    with pytest.raises(TicketError) as info:
        catalog.resolve_macro("Data - Amplify")
    assert "allowlist" in str(info.value)
