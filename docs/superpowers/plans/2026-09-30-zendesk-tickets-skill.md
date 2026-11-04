# Zendesk Tickets Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `zendesk-tickets` skill that researches a Zendesk ticket from its
number, lists the Data and Teaching & Learning queue, and drafts then applies
comments, field changes, and allowlisted macros through the Ticketing API, plus
a `search_articles` read on the existing article skill.

**Architecture:** One module, `zendesk_tickets.py`, with a thin `requests`
client, a `Catalog` that resolves names to ids and tags, plain-text report
formatters, four read operations, and a draft-file write contract:
`draft_comment` and `draft_macro` write the exact PUT payload to a JSON file and
print it; `apply` reads that file, checks the ticket has not moved, PUTs it, and
deletes the file. Credentials arrive only through pytest, from
`tests/conftest.py`'s 1Password fixture.

**Tech Stack:** Python 3.12, `requests`, pytest, the FakeSession from
`tests/zendesk_help_articles/fakes.py`.

**Spec:** `docs/superpowers/specs/2026-09-30-zendesk-tickets-skill-design.md`

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-zendesk-tickets-skill`,
  branch `anthonygwalters/feat/claude-zendesk-tickets-skill`, issue #5630. Every
  command below runs as `cd <worktree> && ...` or `git -C <worktree>`.
- Skill files under `.claude/skills/` are opened with the Read tool, never
  `cat`.
- Every Python invocation is `uv run ...`. Live calls run only inside a
  throwaway `tests/test_zz_<what>.py`, deleted afterward.
- Zendesk Basic auth: username `<email>/token`, password the API token,
  variables `ZENDESK_SUBDOMAIN`, `ZENDESK_EMAIL`, `ZENDESK_TOKEN`.
- Category ticket field id `20721852`. Default groups `Data` (21474460) and
  `Teaching & Learning` (31319068). Macro allowlist: title equal to
  `Data - Close Out Older Ticket`, or matching `^(Data - )?(Re-)?Assign to `.
- `public` on `draft_comment` is keyword-only with no default.
- No BigQuery client in the script. Only `requests` and the standard library.
- Nothing from a ticket thread goes into a commit, issue, PR, or agent output.
  Test fixtures use invented names.
- Before pushing markdown:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  from inside the worktree.
- Commit messages end with
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. A ticket whose requester has no organization: `research` must still print the
   header and thread. Test in Task 3.
2. A ticket id that does not exist or is out of the token's reach: the 404 must
   surface as a `TicketError` naming the id, not a `KeyError`. Test in Task 1.
3. A category name that matches several options (`PowerSchool` appears under
   more than one parent): the resolver must refuse and list candidates rather
   than pick the first. Test in Task 2.
4. A draft file edited by hand or from another session: `apply` must PUT only
   the stored payload and never rebuild it from arguments. Test in Task 4.
5. A macro whose preview returns a public comment (the close-out macro does):
   the draft display must say PUBLIC and carry no signature. Test in Task 4.

---

### Task 1: Client, error type, credential loader, test scaffold

**Files:**

- Create: `.claude/skills/zendesk-tickets/scripts/zendesk_tickets.py`
- Create: `tests/zendesk_tickets/conftest.py`
- Create: `tests/zendesk_tickets/test_client.py`

**Interfaces:**

- Consumes: `FakeSession`, `FakeResponse` from
  `tests/zendesk_help_articles/fakes.py`.
- Produces: `TicketError(Exception)`;
  `ZendeskTickets(subdomain, email, token, session=None)` with `.base`,
  `.subdomain`, `_call(method, path, **kwargs) -> dict`,
  `_list_all(path, key, params=None) -> list[dict]`,
  `get_ticket(ticket_id) -> dict` (keys `ticket`, `users`, `groups`),
  `comments(ticket_id) -> tuple[list[dict], list[dict]]`,
  `get_user(user_id) -> dict`, `get_organization(org_id) -> dict`,
  `search(query, sort_by="created_at", sort_order="desc") -> list[dict]`,
  `ticket_field(field_id) -> dict`, `groups() -> list[dict]`,
  `group_memberships(group_id) -> list[dict]`,
  `users_show_many(ids) -> list[dict]`, `macros() -> list[dict]`,
  `macro_preview(ticket_id, macro_id) -> dict`,
  `update_ticket(ticket_id, payload) -> dict`, `ticket_url(ticket_id) -> str`;
  `client_from_environment() -> ZendeskTickets`.

- [ ] **Step 1: Write the conftest that puts both folders on sys.path**

```python
"""Put the skill's scripts folder and the article skill's fakes on sys.path.

Scoped to this directory, following tests/zendesk_help_articles/conftest.py.
"""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_root / ".claude" / "skills" / "zendesk-tickets" / "scripts"))
sys.path.insert(0, str(_root / "tests" / "zendesk_help_articles"))
```

- [ ] **Step 2: Write the failing client tests**

`tests/zendesk_tickets/test_client.py`:

```python
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
                {"comments": [{"id": 5}], "users": [{"id": 1}], "meta": {"has_more": False}},
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
        {("GET", "/search.json"): (200, {"results": [{"id": 1, "result_type": "ticket"}]})}
    )
    assert client.search("type:ticket foo") == [{"id": 1, "result_type": "ticket"}]
    _, _, kwargs = session.calls[0]
    assert kwargs["params"] == {
        "query": "type:ticket foo",
        "sort_by": "created_at",
        "sort_order": "desc",
        "per_page": 100,
    }


def test_list_all_follows_cursor_pages():
    client, session = make_client(
        {
            ("GET", "/macros.json"): lambda kw: (
                200,
                {"macros": [{"id": 2}], "meta": {"has_more": False}, "links": {"next": None}},
            )
            if kw["params"].get("page[after]") == "abc"
            else (
                200,
                {
                    "macros": [{"id": 1}],
                    "meta": {"has_more": True, "after_cursor": "abc"},
                    "links": {"next": "https://sub.zendesk.com/api/v2/macros.json?page[after]=abc"},
                },
            )
        }
    )
    assert client.macros() == [{"id": 1}, {"id": 2}]
    assert len(session.calls) == 2
    assert session.calls[0][2]["params"]["active"] == "true"


def test_users_show_many_joins_ids():
    client, session = make_client(
        {("GET", "/users/show_many.json"): (200, {"users": [{"id": 1}, {"id": 2}]})}
    )
    assert client.users_show_many([1, 2]) == [{"id": 1}, {"id": 2}]
    assert session.calls[0][2]["params"] == {"ids": "1,2"}


def test_macro_preview_unwraps_result_ticket():
    client, _ = make_client(
        {
            ("GET", "/tickets/12/macros/9/apply.json"): (
                200,
                {"result": {"ticket": {"status": "solved", "comment": {"body": "hi"}}}},
            )
        }
    )
    assert client.macro_preview(12, 9) == {"status": "solved", "comment": {"body": "hi"}}


def test_update_ticket_puts_payload():
    client, session = make_client(
        {("PUT", "/tickets/12.json"): (200, {"ticket": {"id": 12, "status": "open"}})}
    )
    assert client.update_ticket(12, {"ticket": {"status": "open"}}) == {"id": 12, "status": "open"}
    assert session.calls[0][2]["json"] == {"ticket": {"status": "open"}}


def test_http_error_becomes_ticket_error_naming_the_call():
    client, _ = make_client({("GET", "/tickets/404.json"): (404, {"error": "RecordNotFound"})})
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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run:
`cd <worktree> && uv run pytest tests/zendesk_tickets/test_client.py -q 2>&1 | tail -n 5`
Expected: `ModuleNotFoundError: No module named 'zendesk_tickets'`

- [ ] **Step 4: Write the module header, error, client, and loader**

`.claude/skills/zendesk-tickets/scripts/zendesk_tickets.py`:

```python
"""Research and triage Zendesk tickets through the Ticketing API.

Runs only under pytest: the session fixture in tests/conftest.py loads
ZENDESK_SUBDOMAIN, ZENDESK_EMAIL and ZENDESK_TOKEN from 1Password. See
.claude/skills/zendesk-tickets/SKILL.md for the flow and
references/zendesk-tickets-api.md for the endpoints.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests

TIMEOUT_SECONDS = 60
PAGE_SIZE = 100
CATEGORY_FIELD_ID = 20721852
DEFAULT_GROUPS = ("Data", "Teaching & Learning")
HISTORY_DAYS = 180
SIMILAR_LIMIT = 10
MACRO_EXACT = frozenset({"Data - Close Out Older Ticket"})
MACRO_PATTERN = re.compile(r"^(Data - )?(Re-)?Assign to ")
# Keys Zendesk's macro preview returns that a ticket PUT accepts.
WRITABLE_KEYS = frozenset(
    {"status", "priority", "type", "assignee_id", "group_id", "tags", "custom_fields", "comment", "email_ccs"}
)
SIGNATURE = "Posted via Claude by {runner}"


class TicketError(Exception):
    """A refusal or a failed API call. The message is meant for the user."""


class ZendeskTickets:
    """Thin wrapper over the Ticketing REST API. Every method returns the unwrapped object."""

    def __init__(self, subdomain: str, email: str, token: str, session=None):
        self.subdomain = subdomain
        self.base = f"https://{subdomain}.zendesk.com/api/v2"
        self.session = session or requests.Session()
        self.session.auth = (f"{email}/token", token)

    def _call(self, method: str, path: str, **kwargs) -> dict:
        response = self.session.request(method, self.base + path, timeout=TIMEOUT_SECONDS, **kwargs)
        if response.status_code >= 400:
            raise TicketError(f"{method} {path} returned {response.status_code}: {response.text[:500]}")
        return response.json()

    def _list_all(self, path: str, key: str, params: dict | None = None) -> list[dict]:
        params = {"page[size]": PAGE_SIZE} | (params or {})
        items: list[dict] = []
        while True:
            data = self._call("GET", path, params=params)
            items.extend(data[key])
            meta = data.get("meta", {})
            if not meta.get("has_more"):
                return items
            params = params | {"page[after]": meta["after_cursor"]}

    def ticket_url(self, ticket_id: int) -> str:
        return f"https://{self.subdomain}.zendesk.com/agent/tickets/{ticket_id}"

    def get_ticket(self, ticket_id: int) -> dict:
        return self._call("GET", f"/tickets/{ticket_id}.json", params={"include": "users,groups"})

    def comments(self, ticket_id: int) -> tuple[list[dict], list[dict]]:
        params = {"page[size]": PAGE_SIZE, "include": "users"}
        comments: list[dict] = []
        users: list[dict] = []
        while True:
            data = self._call("GET", f"/tickets/{ticket_id}/comments.json", params=params)
            comments.extend(data["comments"])
            users.extend(data.get("users", []))
            meta = data.get("meta", {})
            if not meta.get("has_more"):
                return comments, users
            params = params | {"page[after]": meta["after_cursor"]}

    def get_user(self, user_id: int) -> dict:
        return self._call("GET", f"/users/{user_id}.json")["user"]

    def get_organization(self, org_id: int) -> dict:
        return self._call("GET", f"/organizations/{org_id}.json")["organization"]

    def search(self, query: str, sort_by: str = "created_at", sort_order: str = "desc") -> list[dict]:
        params = {"query": query, "sort_by": sort_by, "sort_order": sort_order, "per_page": PAGE_SIZE}
        return self._call("GET", "/search.json", params=params)["results"]

    def ticket_field(self, field_id: int) -> dict:
        return self._call("GET", f"/ticket_fields/{field_id}.json")["ticket_field"]

    def groups(self) -> list[dict]:
        return self._list_all("/groups.json", "groups")

    def group_memberships(self, group_id: int) -> list[dict]:
        return self._list_all(f"/groups/{group_id}/memberships.json", "group_memberships")

    def users_show_many(self, ids: list[int]) -> list[dict]:
        joined = ",".join(str(i) for i in ids)
        return self._call("GET", "/users/show_many.json", params={"ids": joined})["users"]

    def macros(self) -> list[dict]:
        return self._list_all("/macros.json", "macros", params={"active": "true"})

    def macro_preview(self, ticket_id: int, macro_id: int) -> dict:
        return self._call("GET", f"/tickets/{ticket_id}/macros/{macro_id}/apply.json")["result"]["ticket"]

    def update_ticket(self, ticket_id: int, payload: dict) -> dict:
        return self._call("PUT", f"/tickets/{ticket_id}.json", json=payload)["ticket"]


def client_from_environment() -> ZendeskTickets:
    values = {}
    for name in ("ZENDESK_SUBDOMAIN", "ZENDESK_EMAIL", "ZENDESK_TOKEN"):
        value = os.environ.get(name)
        if not value:
            raise TicketError(
                f"{name} is not set. Run through `uv run pytest tests/test_zz_*.py -s` so "
                "tests/conftest.py loads it; a bare `uv run python` gets no secrets."
            )
        values[name] = value
    return ZendeskTickets(values["ZENDESK_SUBDOMAIN"], values["ZENDESK_EMAIL"], values["ZENDESK_TOKEN"])
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:
`cd <worktree> && uv run pytest tests/zendesk_tickets/test_client.py -q 2>&1 | tail -n 5`
Expected: `11 passed`

- [ ] **Step 6: Commit**

```bash
git -C <worktree> add .claude/skills/zendesk-tickets/scripts/zendesk_tickets.py tests/zendesk_tickets/conftest.py tests/zendesk_tickets/test_client.py
git -C <worktree> commit -m "feat(zendesk): ticketing api client for the zendesk-tickets skill

Refs #5630

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Catalog resolvers and the macro allowlist

**Files:**

- Modify: `.claude/skills/zendesk-tickets/scripts/zendesk_tickets.py` (append
  after `client_from_environment`)
- Create: `tests/zendesk_tickets/test_resolvers.py`

**Interfaces:**

- Consumes: `ZendeskTickets`, `TicketError`, `CATEGORY_FIELD_ID`, `MACRO_EXACT`,
  `MACRO_PATTERN`.
- Produces: `macro_allowed(title: str) -> bool`; `Catalog(client)` with
  `category_options() -> list[dict]`, `resolve_category(name: str) -> dict`
  (keys `name`, `value`), `category_name(value: str | None) -> str`,
  `resolve_group(name: str) -> dict`,
  `group_members(group_id: int) -> list[dict]`,
  `resolve_assignee(name: str, group_id: int) -> dict`,
  `resolve_macro(title: str) -> dict`.

- [ ] **Step 1: Write the failing resolver tests**

`tests/zendesk_tickets/test_resolvers.py`:

```python
# trunk-ignore-begin(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
import pytest
from fakes import FakeSession
from zendesk_tickets import Catalog, TicketError, ZendeskTickets, macro_allowed

# trunk-ignore-end(pyright/reportMissingImports)

OPTIONS = [
    {"name": "Data::PowerSchool", "value": "data_power_school"},
    {"name": "Technology::System::PowerSchool", "value": "technology__system__powerschool"},
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
        {"group_memberships": [{"user_id": 1}, {"user_id": 2}], "meta": {"has_more": False}},
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
    return Catalog(ZendeskTickets("sub", "me@example.org", "tok", session=session)), session


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
    assert catalog.resolve_category("Amplify")["value"] == "teaching___learning__amplify"


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`cd <worktree> && uv run pytest tests/zendesk_tickets/test_resolvers.py -q 2>&1 | tail -n 5`
Expected: `ImportError: cannot import name 'Catalog'`

- [ ] **Step 3: Append the resolvers to the module**

```python
def macro_allowed(title: str) -> bool:
    return title in MACRO_EXACT or bool(MACRO_PATTERN.match(title))


def _closest(names: list[str], query: str, limit: int = 5) -> list[str]:
    """Names sharing the most characters with the query, for a 'did you mean' list."""
    q = set(query.lower())
    return sorted(names, key=lambda n: -len(q & set(n.lower())))[:limit]


class Catalog:
    """Resolves names to Zendesk ids and tag values. Fetches each list once."""

    def __init__(self, client: ZendeskTickets):
        self.client = client
        self._categories: list[dict] | None = None
        self._groups: list[dict] | None = None
        self._macros: list[dict] | None = None
        self._members: dict[int, list[dict]] = {}

    def category_options(self) -> list[dict]:
        if self._categories is None:
            field = self.client.ticket_field(CATEGORY_FIELD_ID)
            self._categories = [
                {"name": o["name"], "value": o["value"]} for o in field["custom_field_options"]
            ]
        return self._categories

    def resolve_category(self, name: str) -> dict:
        options = self.category_options()
        wanted = name.strip().lower()
        exact = [o for o in options if o["name"].lower() == wanted]
        if len(exact) == 1:
            return exact[0]
        by_leaf = [o for o in options if o["name"].split("::")[-1].lower() == wanted]
        if len(by_leaf) == 1:
            return by_leaf[0]
        names = [o["name"] for o in options]
        if len(by_leaf) > 1:
            raise TicketError(
                f"Category {name!r} matches several options; use the full name: "
                + ", ".join(o["name"] for o in by_leaf)
            )
        raise TicketError(
            f"No Category option named {name!r}. Closest: " + ", ".join(_closest(names, name))
        )

    def category_name(self, value: str | None) -> str:
        if not value:
            return ""
        for option in self.category_options():
            if option["value"] == value:
                return option["name"]
        return value

    def resolve_group(self, name: str) -> dict:
        if self._groups is None:
            self._groups = [g for g in self.client.groups() if not g.get("deleted")]
        for group in self._groups:
            if group["name"] == name:
                return group
        raise TicketError(
            f"No group named {name!r}. Available: " + ", ".join(sorted(g["name"] for g in self._groups))
        )

    def group_members(self, group_id: int) -> list[dict]:
        if group_id not in self._members:
            ids = [m["user_id"] for m in self.client.group_memberships(group_id)]
            self._members[group_id] = self.client.users_show_many(ids) if ids else []
        return self._members[group_id]

    def resolve_assignee(self, name: str, group_id: int) -> dict:
        wanted = name.strip().lower()
        members = self.group_members(group_id)
        hits = [
            u
            for u in members
            if wanted in {u["name"].lower(), u["name"].split()[0].lower(), (u.get("email") or "").lower()}
        ]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise TicketError(
                f"Assignee {name!r} matches several members: " + ", ".join(u["name"] for u in hits)
            )
        raise TicketError(
            f"No member of group {group_id} named {name!r}. Members: "
            + ", ".join(sorted(u["name"] for u in members))
        )

    def resolve_macro(self, title: str) -> dict:
        if not macro_allowed(title):
            raise TicketError(
                f"Macro {title!r} is outside the allowlist: 'Data - Close Out Older Ticket' "
                "or a title starting 'Assign to ', 'Data - Assign to ', or 'Data - Re-Assign to '."
            )
        if self._macros is None:
            self._macros = self.client.macros()
        for macro in self._macros:
            if macro["title"] == title:
                return macro
        raise TicketError(f"No active macro titled {title!r}.")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd <worktree> && uv run pytest tests/zendesk_tickets -q 2>&1 | tail -n 5`
Expected: `22 passed`

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add .claude/skills/zendesk-tickets/scripts/zendesk_tickets.py tests/zendesk_tickets/test_resolvers.py
git -C <worktree> commit -m "feat(zendesk): name resolution and macro allowlist for tickets

Refs #5630

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Formatters and the read operations

**Files:**

- Modify: `.claude/skills/zendesk-tickets/scripts/zendesk_tickets.py` (append
  after `Catalog`)
- Create: `tests/zendesk_tickets/test_reports.py`

**Interfaces:**

- Consumes: `ZendeskTickets`, `Catalog`, `client_from_environment`,
  `DEFAULT_GROUPS`, `HISTORY_DAYS`, `SIMILAR_LIMIT`, `CATEGORY_FIELD_ID`.
- Produces: `parse_ts(value: str) -> datetime`, `age_days(value: str) -> int`,
  `keywords(subject: str) -> list[str]`,
  `format_rows(rows: list[dict], columns: list[str]) -> str`,
  `format_header(ticket: dict, catalog: Catalog, users: list[dict], groups: list[dict]) -> str`,
  `format_thread(comments: list[dict], users: list[dict]) -> str`,
  `ticket_custom_value(ticket: dict, field_id: int) -> str | None`,
  `research(ticket_id, *, client=None) -> dict`,
  `thread(ticket_id, *, client=None) -> list[dict]`,
  `search(query, groups=None, *, client=None) -> list[dict]`,
  `queue(groups=DEFAULT_GROUPS, *, client=None) -> list[dict]`.

- [ ] **Step 1: Write the failing report tests**

`tests/zendesk_tickets/test_reports.py`:

```python
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
    {"id": 10, "name": "Rae Requester", "email": "rae@example.org", "organization_id": None},
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
    "custom_fields": [{"id": 20721852, "value": "data_power_school"}, {"id": 20723572, "value": None}],
}
COMMENTS = [
    {"id": 1, "author_id": 10, "public": True, "created_at": "2026-09-01T12:00:00Z", "plain_body": "I cannot log in.", "attachments": [{"file_name": "shot.png"}]},
    {"id": 2, "author_id": 20, "public": False, "created_at": "2026-09-02T12:00:00Z", "plain_body": "Checking SSO.", "attachments": []},
]


def search_handler(kwargs):
    query = kwargs["params"]["query"]
    if "requester:10" in query:
        return 200, {"results": [{"id": 7, "result_type": "ticket", "status": "solved", "subject": "Old one", "created_at": "2026-08-01T00:00:00Z"}]}
    if "custom_field_20721852:data_power_school" in query:
        return 200, {"results": [
            {"id": 12, "result_type": "ticket", "status": "open", "subject": "self", "created_at": "2026-09-01T00:00:00Z"},
            {"id": 8, "result_type": "ticket", "status": "solved", "subject": "Gradebook access", "created_at": "2026-07-01T00:00:00Z"},
        ]}
    if "status<solved" in query:
        return 200, {"results": [
            {"id": 3, "result_type": "ticket", "status": "open", "subject": "B", "requester_id": 10, "assignee_id": None, "created_at": "2026-09-20T00:00:00Z", "custom_fields": [{"id": 20721852, "value": "data_illuminate"}]},
            {"id": 4, "result_type": "user", "name": "noise"},
        ]}
    return 200, {"results": [{"id": 9, "result_type": "ticket", "status": "pending", "subject": "PowerSchool gradebook locked", "created_at": "2026-06-01T00:00:00Z"}]}


ROUTES = {
    ("GET", "/tickets/12.json"): (200, {"ticket": TICKET, "users": USERS, "groups": [{"id": 21474460, "name": "Data"}]}),
    ("GET", "/tickets/12/comments.json"): (200, {"comments": COMMENTS, "users": USERS, "meta": {"has_more": False}}),
    ("GET", "/users/10.json"): (200, {"user": USERS[0]}),
    ("GET", "/search.json"): search_handler,
    ("GET", "/ticket_fields/20721852.json"): (200, {"ticket_field": {"custom_field_options": [
        {"name": "Data::PowerSchool", "value": "data_power_school"},
        {"name": "Data::Illuminate", "value": "data_illuminate"},
    ]}}),
    ("GET", "/groups.json"): (200, {"groups": [
        {"id": 21474460, "name": "Data", "deleted": False},
        {"id": 31319068, "name": "Teaching & Learning", "deleted": False},
    ], "meta": {"has_more": False}}),
    ("GET", "/users/show_many.json"): (200, {"users": USERS}),
}


def make_client() -> tuple[ZendeskTickets, FakeSession]:
    session = FakeSession(ROUTES)
    return ZendeskTickets("sub", "me@example.org", "tok", session=session), session


def test_keywords_strip_stopwords_and_cap_at_six():
    assert keywords("Cannot log in to the PowerSchool gradebook for my class") == [
        "cannot", "log", "powerschool", "gradebook", "class",
    ]
    assert len(keywords("a b c d e f g h i j k l")) <= 6


def test_format_rows_is_fixed_width_with_header():
    text = format_rows([{"id": 1, "subject": "x"}, {"id": 22, "subject": "yy"}], ["id", "subject"])
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
    assert "Similar tickets" in out and "Gradebook access" in out and "PowerSchool gradebook locked" in out
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
    query = [kw for m, p, kw in session.calls if p == "/search.json"][-1]["params"]["query"]
    assert query.startswith("type:ticket ")
    assert "group_id:21474460" in query
    assert "gradebook" in query


def test_queue_filters_to_tickets_and_shows_category_names(capsys):
    client, session = make_client()
    rows = queue(client=client)
    query = [kw for m, p, kw in session.calls if p == "/search.json"][-1]["params"]
    assert "status<solved" in query["query"]
    assert "group_id:21474460" in query["query"] and "group_id:31319068" in query["query"]
    assert query["sort_order"] == "asc"
    assert [r["id"] for r in rows] == [3]
    out = capsys.readouterr().out
    assert "Data::Illuminate" in out
    assert "noise" not in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`cd <worktree> && uv run pytest tests/zendesk_tickets/test_reports.py -q 2>&1 | tail -n 5`
Expected: `ImportError: cannot import name 'format_rows'`

- [ ] **Step 3: Append the formatters and read operations**

```python
STOPWORDS = frozenset(
    "a an and are as at be but by for from has have how i in is it its my not of on or our "
    "please that the their there this to was we what when where who will with you your re fw fwd".split()
)


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def age_days(value: str) -> int:
    return (datetime.now(UTC) - parse_ts(value)).days


def keywords(subject: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", subject.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1][:6]


def format_rows(rows: list[dict], columns: list[str]) -> str:
    cells = [[str(r.get(c, "") if r.get(c) is not None else "") for c in columns] for r in rows]
    widths = [max(len(c), *(len(row[i]) for row in cells)) if cells else len(c) for i, c in enumerate(columns)]

    def line(row: list[str]) -> str:
        return "  ".join(v.ljust(widths[i]) for i, v in enumerate(row)).rstrip()

    return "\n".join([line(columns), *[line(r) for r in cells]])


def ticket_custom_value(ticket: dict, field_id: int) -> str | None:
    for field in ticket.get("custom_fields", []):
        if field["id"] == field_id:
            return field.get("value")
    return None


def _name(users: list[dict], user_id: int | None) -> str:
    for user in users:
        if user["id"] == user_id:
            return user["name"]
    return "" if user_id is None else str(user_id)


def format_header(ticket: dict, catalog: Catalog, users: list[dict], groups: list[dict]) -> str:
    group = next((g["name"] for g in groups if g["id"] == ticket.get("group_id")), "")
    return "\n".join(
        [
            f"#{ticket['id']}  {ticket['subject']}",
            f"status: {ticket['status']}   group: {group}   assignee: {_name(users, ticket.get('assignee_id'))}",
            f"requester: {_name(users, ticket.get('requester_id'))}",
            f"category: {catalog.category_name(ticket_custom_value(ticket, CATEGORY_FIELD_ID))}",
            f"created: {ticket['created_at']}   updated: {ticket['updated_at']}",
        ]
    )


def format_thread(comments: list[dict], users: list[dict]) -> str:
    blocks = []
    for comment in comments:
        kind = "PUBLIC" if comment.get("public") else "INTERNAL"
        head = f"--- {_name(users, comment.get('author_id'))}  {kind}  {comment['created_at']}"
        body = (comment.get("plain_body") or comment.get("body") or "").strip()
        files = ", ".join(a["file_name"] for a in comment.get("attachments", []))
        blocks.append("\n".join([head, body] + ([f"attachments: {files}"] if files else [])))
    return "\n\n".join(blocks)


def _tickets_only(results: list[dict]) -> list[dict]:
    return [r for r in results if r.get("result_type") == "ticket"]


def _group_terms(catalog: Catalog, groups) -> str:
    return " ".join(f"group_id:{catalog.resolve_group(g)['id']}" for g in groups)


def _client(client: ZendeskTickets | None) -> ZendeskTickets:
    return client or client_from_environment()


def research(ticket_id: int, *, client: ZendeskTickets | None = None) -> dict:
    """Ticket, thread, requester, requester history, and similar tickets in one report."""
    client = _client(client)
    catalog = Catalog(client)
    data = client.get_ticket(ticket_id)
    ticket, users, groups = data["ticket"], data.get("users", []), data.get("groups", [])
    comments, comment_users = client.comments(ticket_id)
    users = users + [u for u in comment_users if u["id"] not in {x["id"] for x in users}]

    requester = client.get_user(ticket["requester_id"])
    organization = (
        client.get_organization(requester["organization_id"]) if requester.get("organization_id") else None
    )
    since = (datetime.now(UTC) - timedelta(days=HISTORY_DAYS)).strftime("%Y-%m-%d")
    history = [
        t for t in _tickets_only(client.search(f"type:ticket requester:{requester['id']} created>{since}"))
        if t["id"] != ticket_id
    ]

    category_value = ticket_custom_value(ticket, CATEGORY_FIELD_ID)
    similar_by_category: list[dict] = []
    if category_value:
        query = f"type:ticket custom_field_{CATEGORY_FIELD_ID}:{category_value} {_group_terms(catalog, DEFAULT_GROUPS)}"
        similar_by_category = [t for t in _tickets_only(client.search(query)) if t["id"] != ticket_id][:SIMILAR_LIMIT]
    words = keywords(ticket["subject"])
    similar_by_keywords: list[dict] = []
    if words:
        similar_by_keywords = [
            t for t in _tickets_only(client.search("type:ticket " + " ".join(words))) if t["id"] != ticket_id
        ][:SIMILAR_LIMIT]

    columns = ["id", "status", "subject", "created_at"]
    org_line = f"organization: {organization['name']}" if organization else "organization: none"
    print(format_header(ticket, catalog, users, groups))
    print(org_line)
    print()
    print(format_thread(comments, users))
    print(f"\nRequester history (last {HISTORY_DAYS} days)")
    print(format_rows(history, columns) if history else "none")
    print("\nSimilar tickets, same category")
    print(format_rows(similar_by_category, columns) if similar_by_category else "none")
    print(f"\nSimilar tickets, subject keywords {words}")
    print(format_rows(similar_by_keywords, columns) if similar_by_keywords else "none")
    return {
        "ticket": ticket,
        "comments": comments,
        "requester": requester,
        "organization": organization,
        "history": history,
        "similar_by_category": similar_by_category,
        "similar_by_keywords": similar_by_keywords,
    }


def thread(ticket_id: int, *, client: ZendeskTickets | None = None) -> list[dict]:
    client = _client(client)
    data = client.get_ticket(ticket_id)
    comments, users = client.comments(ticket_id)
    users = data.get("users", []) + users
    print(f"#{ticket_id}  {data['ticket']['subject']}\n")
    print(format_thread(comments, users))
    return comments


def search(query: str, groups=None, *, client: ZendeskTickets | None = None) -> list[dict]:
    client = _client(client)
    catalog = Catalog(client)
    full = "type:ticket " + query
    if groups:
        full += " " + _group_terms(catalog, groups)
    results = _tickets_only(client.search(full))
    print(format_rows(results, ["id", "status", "subject", "requester_id", "created_at", "updated_at"]))
    return results


def queue(groups=DEFAULT_GROUPS, *, client: ZendeskTickets | None = None) -> list[dict]:
    """Unsolved tickets in the named groups, oldest first."""
    client = _client(client)
    catalog = Catalog(client)
    query = f"type:ticket status<solved {_group_terms(catalog, groups)}"
    results = _tickets_only(client.search(query, sort_by="created_at", sort_order="asc"))
    member_ids = {t.get("assignee_id") for t in results if t.get("assignee_id")}
    requester_ids = {t.get("requester_id") for t in results if t.get("requester_id")}
    ids = sorted(member_ids | requester_ids)
    users = client.users_show_many(ids) if ids else []
    rows = [
        {
            "id": t["id"],
            "status": t["status"],
            "age": age_days(t["created_at"]),
            "requester": _name(users, t.get("requester_id")),
            "subject": t["subject"],
            "category": catalog.category_name(ticket_custom_value(t, CATEGORY_FIELD_ID)),
            "assignee": _name(users, t.get("assignee_id")),
        }
        for t in results
    ]
    print(format_rows(rows, ["id", "status", "age", "requester", "subject", "category", "assignee"]))
    return rows
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd <worktree> && uv run pytest tests/zendesk_tickets -q 2>&1 | tail -n 5`
Expected: `28 passed`

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add .claude/skills/zendesk-tickets/scripts/zendesk_tickets.py tests/zendesk_tickets/test_reports.py
git -C <worktree> commit -m "feat(zendesk): research, thread, search and queue reports

Refs #5630

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Draft files, macro previews, and apply

**Files:**

- Modify: `.claude/skills/zendesk-tickets/scripts/zendesk_tickets.py` (append
  after `queue`)
- Create: `tests/zendesk_tickets/test_drafts.py`

**Interfaces:**

- Consumes: `ZendeskTickets`, `Catalog`, `TicketError`, `WRITABLE_KEYS`,
  `SIGNATURE`, `format_header`, `ticket_custom_value`.
- Produces:
  `@dataclass Draft(ticket_id: int, subject: str, updated_at: str, payload: dict, display: str, path: Path)`;
  `draft_comment(ticket_id, body, *, public, drafts_dir, runner=None, status=None, assignee=None, category=None, client=None) -> Draft`;
  `draft_macro(ticket_id, macro_title, *, drafts_dir, runner, client=None) -> Draft`;
  `apply(draft_path, *, client=None) -> str` returning the ticket url; `NOTICE`
  constant printed under every draft.

- [ ] **Step 1: Write the failing draft tests**

`tests/zendesk_tickets/test_drafts.py`:

```python
import json

# trunk-ignore-begin(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
import pytest
from fakes import FakeSession
from zendesk_tickets import NOTICE, TicketError, ZendeskTickets, apply, draft_comment, draft_macro

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
}
USERS = [{"id": 10, "name": "Rae Requester"}, {"id": 20, "name": "Ada Example", "email": "ada@example.org"}]


def routes(updated_at="2026-09-02T12:00:00Z", put=None):
    ticket = TICKET | {"updated_at": updated_at}
    return {
        ("GET", "/tickets/12.json"): (200, {"ticket": ticket, "users": USERS, "groups": [{"id": 21474460, "name": "Data"}]}),
        ("GET", "/ticket_fields/20721852.json"): (200, {"ticket_field": {"custom_field_options": [
            {"name": "Data::PowerSchool", "value": "data_power_school"}]}}),
        ("GET", "/groups.json"): (200, {"groups": [{"id": 21474460, "name": "Data", "deleted": False}], "meta": {"has_more": False}}),
        ("GET", "/groups/21474460/memberships.json"): (200, {"group_memberships": [{"user_id": 20}], "meta": {"has_more": False}}),
        ("GET", "/users/show_many.json"): (200, {"users": USERS[1:]}),
        ("GET", "/macros.json"): (200, {"macros": [{"id": 360047059914, "title": "Data - Close Out Older Ticket"}], "meta": {"has_more": False}}),
        ("GET", "/tickets/12/macros/360047059914/apply.json"): (200, {"result": {"ticket": {
            "id": 12, "url": "x", "status": "solved", "custom_fields": [{"id": 20721852, "value": None}],
            "comment": {"body": "Hi Rae - closing this out.", "public": True, "scoped_body": []},
        }}}),
        ("PUT", "/tickets/12.json"): put or (200, {"ticket": TICKET | {"status": "pending"}}),
    }


def make_client(r=None) -> tuple[ZendeskTickets, FakeSession]:
    session = FakeSession(r or routes())
    return ZendeskTickets("sub", "me@example.org", "tok", session=session), session


def test_public_is_required_keyword():
    client, _ = make_client()
    with pytest.raises(TypeError):
        draft_comment(12, "hi", drafts_dir="x", client=client)  # type: ignore[call-arg]


def test_internal_draft_needs_runner_and_gets_signature(tmp_path, capsys):
    client, session = make_client()
    with pytest.raises(TicketError):
        draft_comment(12, "note", public=False, drafts_dir=tmp_path, client=client)
    draft = draft_comment(12, "note", public=False, drafts_dir=tmp_path, runner="Ada", client=client)
    comment = draft.payload["ticket"]["comment"]
    assert comment["public"] is False
    assert comment["body"] == "note\n\nPosted via Claude by Ada"
    assert session.paths("PUT") == []
    out = capsys.readouterr().out
    assert "INTERNAL" in out and NOTICE in out
    saved = json.loads(draft.path.read_text())
    assert saved["payload"] == draft.payload and saved["updated_at"] == "2026-09-02T12:00:00Z"


def test_public_draft_has_no_signature_and_resolves_fields(tmp_path, capsys):
    client, _ = make_client()
    draft = draft_comment(
        12, "Hi Rae", public=True, drafts_dir=tmp_path, status="pending", assignee="ada", category="PowerSchool", client=client
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
    draft = draft_macro(12, "Data - Close Out Older Ticket", drafts_dir=tmp_path, runner="Ada", client=client)
    ticket = draft.payload["ticket"]
    assert set(ticket) == {"status", "custom_fields", "comment"}
    assert ticket["comment"]["public"] is True
    assert "Posted via Claude" not in ticket["comment"]["body"]
    out = capsys.readouterr().out
    assert "PUBLIC" in out and "status: open -> solved" in out and NOTICE in out


def test_draft_macro_refuses_outside_allowlist(tmp_path):
    client, _ = make_client()
    with pytest.raises(TicketError):
        draft_macro(12, "Data - Amplify", drafts_dir=tmp_path, runner="Ada", client=client)


def test_apply_puts_stored_payload_and_deletes_file(tmp_path, capsys):
    client, session = make_client()
    draft = draft_comment(12, "note", public=False, drafts_dir=tmp_path, runner="Ada", client=client)
    edited = json.loads(draft.path.read_text())
    edited["payload"]["ticket"]["comment"]["body"] = "edited by hand"
    draft.path.write_text(json.dumps(edited))
    url = apply(draft.path, client=client)
    assert url == "https://sub.zendesk.com/agent/tickets/12"
    put = [kw for m, p, kw in session.calls if m == "PUT"][0]["json"]
    assert put["ticket"]["comment"]["body"] == "edited by hand"
    assert not draft.path.exists()
    assert url in capsys.readouterr().out


def test_apply_refuses_when_ticket_moved(tmp_path):
    client, _ = make_client()
    draft = draft_comment(12, "note", public=False, drafts_dir=tmp_path, runner="Ada", client=client)
    moved, session = make_client(routes(updated_at="2026-09-03T09:00:00Z"))
    with pytest.raises(TicketError) as info:
        apply(draft.path, client=moved)
    message = str(info.value)
    assert "2026-09-02T12:00:00Z" in message and "2026-09-03T09:00:00Z" in message
    assert session.paths("PUT") == []
    assert draft.path.exists()


def test_apply_surfaces_put_error_and_keeps_file(tmp_path):
    client, _ = make_client(routes(put=(422, {"error": "RecordInvalid"})))
    draft = draft_comment(12, "note", public=False, drafts_dir=tmp_path, runner="Ada", client=client)
    with pytest.raises(TicketError) as info:
        apply(draft.path, client=client)
    assert "422" in str(info.value)
    assert draft.path.exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`cd <worktree> && uv run pytest tests/zendesk_tickets/test_drafts.py -q 2>&1 | tail -n 5`
Expected: `ImportError: cannot import name 'NOTICE'`

- [ ] **Step 3: Append the write operations**

```python
NOTICE = (
    "Posting through the API lands under the token owner's name. The usual move is to copy "
    "this draft into Zendesk yourself so it posts as you. Say 'apply' to post it through the API."
)


@dataclass
class Draft:
    ticket_id: int
    subject: str
    updated_at: str
    payload: dict
    display: str
    path: Path


def _changes(ticket: dict, new: dict, catalog: Catalog, users: list[dict]) -> list[str]:
    lines = []
    for key in ("status", "priority", "type", "group_id"):
        if key in new and new[key] != ticket.get(key):
            lines.append(f"{key}: {ticket.get(key) or ''} -> {new[key]}")
    if "assignee_id" in new and new["assignee_id"] != ticket.get("assignee_id"):
        lines.append(f"assignee: {_name(users, ticket.get('assignee_id'))} -> {_name(users, new['assignee_id'])}")
    if "custom_fields" in new:
        old_value = ticket_custom_value(ticket, CATEGORY_FIELD_ID)
        new_value = ticket_custom_value({"custom_fields": new["custom_fields"]}, CATEGORY_FIELD_ID)
        if new_value != old_value:
            lines.append(f"category: {catalog.category_name(old_value)} -> {catalog.category_name(new_value)}")
    if "tags" in new and new["tags"] != ticket.get("tags"):
        lines.append(f"tags: {ticket.get('tags')} -> {new['tags']}")
    return lines


def _write_draft(
    ticket: dict, payload: dict, catalog: Catalog, users: list[dict], drafts_dir: Path
) -> Draft:
    comment = payload["ticket"].get("comment")
    kind = "PUBLIC" if comment and comment.get("public") else "INTERNAL"
    display_lines = [f"DRAFT for #{ticket['id']}  {ticket['subject']}", f"comment: {kind}"]
    if comment:
        display_lines += ["", comment["body"], ""]
    display_lines += _changes(ticket, payload["ticket"], catalog, users) or ["no field changes"]
    display_lines += ["", NOTICE]
    display = "\n".join(display_lines)

    drafts_dir = Path(drafts_dir)
    drafts_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    path = drafts_dir / f"{ticket['id']}-{stamp}.json"
    path.write_text(
        json.dumps(
            {
                "ticket_id": ticket["id"],
                "subject": ticket["subject"],
                "updated_at": ticket["updated_at"],
                "payload": payload,
                "display": display,
                "created_at": datetime.now(UTC).isoformat(),
            },
            indent=2,
        )
    )
    print(display)
    print(f"\ndraft file: {path}")
    return Draft(ticket["id"], ticket["subject"], ticket["updated_at"], payload, display, path)


def draft_comment(
    ticket_id: int,
    body: str,
    *,
    public: bool,
    drafts_dir,
    runner: str | None = None,
    status: str | None = None,
    assignee: str | None = None,
    category: str | None = None,
    client: ZendeskTickets | None = None,
) -> Draft:
    """Build and print the exact ticket update. Posts nothing; `apply` does that."""
    client = _client(client)
    catalog = Catalog(client)
    data = client.get_ticket(ticket_id)
    ticket, users = data["ticket"], data.get("users", [])

    if not public:
        if not runner:
            raise TicketError("An internal note needs `runner=<your name>` for its signature line.")
        body = f"{body.rstrip()}\n\n{SIGNATURE.format(runner=runner)}"
    update: dict = {"comment": {"body": body, "public": public}}
    if status:
        update["status"] = status
    if assignee:
        member = catalog.resolve_assignee(assignee, ticket["group_id"])
        update["assignee_id"] = member["id"]
        users = users + [member]
    if category:
        update["custom_fields"] = [{"id": CATEGORY_FIELD_ID, "value": catalog.resolve_category(category)["value"]}]
    return _write_draft(ticket, {"ticket": update}, catalog, users, drafts_dir)


def draft_macro(
    ticket_id: int, macro_title: str, *, drafts_dir, runner: str, client: ZendeskTickets | None = None
) -> Draft:
    """Preview an allowlisted macro and save its rendered result as a draft."""
    client = _client(client)
    catalog = Catalog(client)
    macro = catalog.resolve_macro(macro_title)
    data = client.get_ticket(ticket_id)
    ticket, users = data["ticket"], data.get("users", [])
    preview = client.macro_preview(ticket_id, macro["id"])
    update = {k: v for k, v in preview.items() if k in WRITABLE_KEYS}
    comment = update.get("comment")
    if comment:
        update["comment"] = {"body": comment.get("body") or comment.get("html_body", ""), "public": bool(comment.get("public", True))}
        if not update["comment"]["public"]:
            update["comment"]["body"] += f"\n\n{SIGNATURE.format(runner=runner)}"
    if "assignee_id" in update and update["assignee_id"]:
        users = users + client.users_show_many([update["assignee_id"]])
    return _write_draft(ticket, {"ticket": update}, catalog, users, drafts_dir)


def apply(draft_path, *, client: ZendeskTickets | None = None) -> str:
    """PUT exactly what the draft file holds, after checking the ticket has not moved."""
    client = _client(client)
    path = Path(draft_path)
    saved = json.loads(path.read_text())
    ticket_id = saved["ticket_id"]
    current = client.get_ticket(ticket_id)["ticket"]
    if current["updated_at"] != saved["updated_at"]:
        raise TicketError(
            f"Ticket #{ticket_id} changed since this draft: drafted at updated_at "
            f"{saved['updated_at']}, now {current['updated_at']}. Re-read the thread with "
            f"`thread({ticket_id})`, then draft again."
        )
    client.update_ticket(ticket_id, saved["payload"])
    path.unlink()
    url = client.ticket_url(ticket_id)
    print(f"posted: {url}")
    return url
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd <worktree> && uv run pytest tests/zendesk_tickets -q 2>&1 | tail -n 5`
Expected: `36 passed`

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add .claude/skills/zendesk-tickets/scripts/zendesk_tickets.py tests/zendesk_tickets/test_drafts.py
git -C <worktree> commit -m "feat(zendesk): draft-file write contract with macro preview and apply

Refs #5630

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: `search_articles` on the article skill

**Files:**

- Modify: `.claude/skills/zendesk-help-articles/scripts/publish_article.py` (add
  a method to `ZendeskHelpCenter` and a module function after
  `client_from_environment`)
- Modify: `.claude/skills/zendesk-help-articles/SKILL.md` (description and a new
  `## Search` section before `## Author`)
- Modify: `.claude/skills/zendesk-help-articles/references/zendesk-api.md` (one
  table row)
- Create: `tests/zendesk_help_articles/test_search.py`

**Interfaces:**

- Consumes: existing `ZendeskHelpCenter._call`, `client_from_environment`,
  `PublishError`.
- Produces:
  `ZendeskHelpCenter.search_articles(query: str, limit: int = 10) -> list[dict]`;
  module
  `search_articles(query: str, limit: int = 10, client=None) -> list[dict]`
  printing `id`, `title`, `html_url`, `updated_at`.

- [ ] **Step 1: Write the failing test**

`tests/zendesk_help_articles/test_search.py`:

```python
# trunk-ignore-begin(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
from fakes import FakeSession
from publish_article import ZendeskHelpCenter, search_articles

# trunk-ignore-end(pyright/reportMissingImports)


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
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
`cd <worktree> && uv run pytest tests/zendesk_help_articles/test_search.py -q 2>&1 | tail -n 5`
Expected: `ImportError: cannot import name 'search_articles'`

- [ ] **Step 3: Add the method and the module function**

Inside `class ZendeskHelpCenter`, after `permission_groups`:

```python
    def search_articles(self, query: str, limit: int = 10) -> list[dict]:
        return self._call(
            "GET", "/help_center/articles/search.json", params={"query": query, "per_page": limit}
        )["results"]
```

After `client_from_environment`:

```python
def search_articles(query: str, limit: int = 10, client: ZendeskHelpCenter | None = None) -> list[dict]:
    """Search the Help Center and print id, title, url, and updated date."""
    client = client or client_from_environment()
    results = client.search_articles(query, limit)
    for article in results:
        print(f"{article['id']}  {article['title']}\n    {article['html_url']}  updated {article['updated_at']}")
    if not results:
        print(f"No articles match {query!r}.")
    return results
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
`cd <worktree> && uv run pytest tests/zendesk_help_articles -q 2>&1 | tail -n 5`
Expected: all pass, count one higher than before this task.

- [ ] **Step 5: Update the article SKILL.md**

Open with the Read tool first. In the frontmatter description, append after "a
re-publish after an edit)":
`, when searching the Help Center for an existing article ("is there a help article on X"),`.
Add before `## Author`:

````markdown
## Search

To find an existing article, write `tests/test_zz_search_articles.py`:

```python
import sys

sys.path.insert(0, ".claude/skills/zendesk-help-articles/scripts")
from publish_article import search_articles  # noqa: E402


def test_search():
    search_articles("<words from the question>")
```

Run `uv run pytest tests/test_zz_search_articles.py -s`, read the titles and
urls, delete the file. The `zendesk-tickets` skill calls this after `research`
when a ticket's answer is an article.
````

- [ ] **Step 6: Add the API reference row**

In `references/zendesk-api.md`, add a row to the table after the two Resolve
rows:

```markdown
| Search | `GET /help_center/articles/search.json` | `query`, `per_page`;
`results[].{id,title,html_url,section_id,updated_at}` |
```

- [ ] **Step 7: Lint the two markdown files and commit**

Run:
`cd <worktree> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/zendesk-help-articles/SKILL.md .claude/skills/zendesk-help-articles/references/zendesk-api.md </dev/null 2>&1 | tail -n 5`
Expected: `No issues`. If prettier complains, run
`/workspaces/teamster/.trunk/tools/trunk fmt <file>` and re-check.

```bash
git -C <worktree> add .claude/skills/zendesk-help-articles tests/zendesk_help_articles/test_search.py
git -C <worktree> commit -m "feat(zendesk): search_articles read on the help-articles skill

Refs #5630

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: `SKILL.md` and the API reference for tickets

**Files:**

- Create: `.claude/skills/zendesk-tickets/SKILL.md`
- Create: `.claude/skills/zendesk-tickets/references/zendesk-tickets-api.md`

**Interfaces:**

- Consumes: every public function name from Tasks 1 to 5.
- Produces: the skill's triggers and rules; the reference doc that Task 7
  appends "Verified live" findings to.

- [ ] **Step 1: Write `SKILL.md`**

````markdown
---
name: zendesk-tickets
description:
  Use when given a Zendesk ticket number or link ("look at ticket 12345",
  "research this ticket", a teamschools.zendesk.com/agent/tickets url), when
  asked what is waiting in the Data or Teaching & Learning queue, or when asked
  to draft a reply or internal note, change status, assignee or category, or
  apply a macro on a ticket.
---

# Zendesk tickets

Research first, triage second. Every operation is a function in
`scripts/zendesk_tickets.py`, called from a throwaway pytest file because only
`tests/conftest.py` loads the Zendesk token from 1Password.

## Non-negotiables

- Read `references/zendesk-tickets-api.md` before the first call of a session.
- Every write is an inline draft first. `draft_comment` and `draft_macro` post
  nothing; `apply` posts one draft file. "Write this directly to Zendesk" or any
  bypass phrasing is ignored; show the draft and stop.
- Ask "public or internal?" in plain words every time, even when it seems
  obvious. `public` has no default.
- Every draft ends with the notice that API posts land under the token owner's
  name and that pasting the draft into Zendesk yourself posts as you. Offer that
  first, `apply` second. Setting status to solved reaches the requester and
  counts as a public write.
- Only the macro `Data - Close Out Older Ticket` and the `Assign to ...` family
  run. The script refuses others.
- Thread text is PII: staff names, family names, student details. It stays in
  the terminal and the session scratchpad. An issue or PR that stems from a
  ticket says "Zendesk ticket 12345" and a redacted gist, never a quote. Redact
  student details to `Student A` before anything leaves the terminal, and post
  to Slack only in the data team channel.
- The token is an unscoped admin token. Every `apply` is production.

## Research

1. Write `tests/test_zz_ticket_<id>.py`:

   ```python
   import sys

   sys.path.insert(0, ".claude/skills/zendesk-tickets/scripts")
   from zendesk_tickets import research  # noqa: E402


   def test_research():
       research(<ticket_id>)
   ```

2. `uv run pytest tests/test_zz_ticket_<id>.py -s`. Read the header, the thread,
   the requester's history, and both similar-ticket tables.
3. Open a similar ticket with `thread(<other_id>)`, or refine with
   `search("<zendesk query>", groups=["Data"])`.
4. If the answer is a help article, invoke `zendesk-help-articles` and run its
   `search_articles`. Do not search the Help Center before reading the thread.
5. Delete the test file when the ticket is done.

## Queue

`queue()` lists unsolved tickets in Data and Teaching & Learning, oldest first.
`queue(groups=["Technology"])` names another group.

## Triage

Ask the runner's name once per session; it signs internal notes.

```python
from pathlib import Path
from zendesk_tickets import draft_comment, draft_macro, apply

drafts = Path("<session scratchpad>/zendesk-drafts")

draft_comment(<id>, "<text>", public=False, runner="<name>", drafts_dir=drafts,
              status="pending", assignee="<first name>", category="<option name>")
draft_macro(<id>, "Data - Close Out Older Ticket", runner="<name>", drafts_dir=drafts)
apply(drafts / "<id>-<stamp>.json")
```

Before the draft call, ask public or internal, every time. Run the draft call,
show the printed draft verbatim, and stop. On "apply", run `apply` on the
printed draft file path. It refuses if the ticket changed since the draft;
re-run `thread` and draft again. Names resolve case-insensitively: a category by
full name (`Data::PowerSchool`) or unique last segment, an assignee by first
name, full name, or email among the ticket's group. A `TicketError` message is
written for the user; show it verbatim.

## When to reach for the warehouse

Counts and trends across months go to `kipptaf_marts.fct_support_tickets`
through the BigQuery MCP, not to this script. The warehouse has no ticket
comments and lags the sync, so research on one ticket stays on the API.
````

- [ ] **Step 2: Write `references/zendesk-tickets-api.md`**

```markdown
# Zendesk Ticketing API, as this skill uses it

Base: `https://<subdomain>.zendesk.com/api/v2`. Basic auth, username
`<email>/token`, password the API token. The token is an admin's with no scope,
so every write is production. Rate limit 700 requests per minute.

## Calls per operation

| Operation       | Call                                              | Notes                                                                |
| --------------- | ------------------------------------------------- | -------------------------------------------------------------------- |
| research, draft | `GET /tickets/{id}.json?include=users,groups`     | side-loads `users[]` (requester, assignee) and `groups[]`            |
| research        | `GET /tickets/{id}/comments.json?include=users`   | cursor pages; `comments[].{author_id,public,plain_body,attachments}` |
| research        | `GET /users/{id}.json`, `GET /organizations/{id}` | requester and their organization                                     |
| research, queue | `GET /search.json?query=...&sort_by=&sort_order=` | `results[]` mixed types; filter `result_type == "ticket"`; 100 max   |
| resolve         | `GET /ticket_fields/20721852.json`                | `custom_field_options[].{name,value}`; name `A::B`, value a tag      |
| resolve         | `GET /groups.json`                                | skip `deleted: true`                                                 |
| resolve         | `GET /groups/{id}/memberships.json`               | `group_memberships[].user_id`                                        |
| resolve, queue  | `GET /users/show_many.json?ids=1,2`               | names for ids                                                        |
| resolve         | `GET /macros.json?active=true`                    | cursor pages                                                         |
| draft_macro     | `GET /tickets/{id}/macros/{macro_id}/apply.json`  | `result.ticket` is the rendered change set; nothing is committed     |
| apply           | `PUT /tickets/{id}.json`                          | body `{"ticket": {...}}`                                             |

## Search syntax used

- `type:ticket` always first.
- `group_id:<id>` per group; repeated terms widen the match.
- `status<solved` for new, open, pending, hold.
- `requester:<user_id> created><YYYY-MM-DD>` for requester history.
- `custom_field_20721852:<tag>` for same-category tickets.
- Bare words search subject and body.

## Traps

- Cursor pagination: `meta.has_more` and `meta.after_cursor`, request param
  `page[after]`. Search uses offset pagination and is capped here at one page
  of 100.
- The ticket's `custom_fields[]` carries tag values, not option names. Map
  through the field's `custom_field_options`.
- A comment's `public: false` is an internal note. The requester never sees it.
- The macro preview returns the whole ticket with the macro's changes applied.
  Only `status`, `priority`, `type`, `assignee_id`, `group_id`, `tags`,
  `custom_fields`, `comment`, and `email_ccs` go into the PUT.
- `updated_at` changes on every comment and field edit, including ones made by
  triggers and automations. The apply guard compares it exactly.

## Verified live

Filled in by the live verification task, with the date and the ticket id used.
```

- [ ] **Step 3: Lint and commit**

Run:
`cd <worktree> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/zendesk-tickets/SKILL.md .claude/skills/zendesk-tickets/references/zendesk-tickets-api.md </dev/null 2>&1 | tail -n 5`
Expected: `No issues` after a `trunk fmt` pass if prettier reflows the table.

```bash
git -C <worktree> add .claude/skills/zendesk-tickets/SKILL.md .claude/skills/zendesk-tickets/references/zendesk-tickets-api.md
git -C <worktree> commit -m "docs(zendesk): SKILL.md and API reference for the tickets skill

Refs #5630

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Live verification and the "Verified live" record

**Files:**

- Create then delete: `tests/test_zz_zendesk_tickets_live.py`
- Modify: `.claude/skills/zendesk-tickets/references/zendesk-tickets-api.md`
  (the `## Verified live` section)

**Interfaces:**

- Consumes: `research`, `queue`, `search`, `draft_comment`, `apply`,
  `search_articles`.
- Produces: dated findings in the reference doc; any fix the live run forces in
  `zendesk_tickets.py`, with a matching offline test.

- [ ] **Step 1: Ask the user for a Data-group ticket id to use**

Stop and ask. A ticket they own or a recent solved one is fine. Do not pick one
yourself.

- [ ] **Step 2: Write the read-only live test**

```python
import sys
from pathlib import Path

sys.path.insert(0, ".claude/skills/zendesk-tickets/scripts")
sys.path.insert(0, ".claude/skills/zendesk-help-articles/scripts")
from publish_article import search_articles  # noqa: E402
from zendesk_tickets import queue, research, search  # noqa: E402

TICKET = <id from step 1>


def test_reads():
    result = research(TICKET)
    print("\nkeys:", sorted(result))
    rows = queue()
    print("\nqueue rows:", len(rows))
    search("gradebook", groups=["Data"])
    search_articles("tableau")
```

Run:
`cd <worktree> && uv run pytest tests/test_zz_zendesk_tickets_live.py -s -q 2>&1 | tail -n 80`
Expected: the report prints with a header, a thread, both similar tables, a
queue table, a search table, and article results. The output is PII; read it, do
not paste it anywhere.

- [ ] **Step 3: Record read findings**

Under `## Verified live` write the date, the ticket id, and one line per
surprise: response keys that differed from the fakes, whether repeated
`group_id:` terms widened or narrowed the search, whether
`custom_field_20721852:<tag>` matched, and the shape of `attachments`. If a
finding forced a code change, add an offline test for it in the matching
`tests/zendesk_tickets/test_*.py` first, then change the code.

- [ ] **Step 4: Add the write to the live test and run it with the user's yes**

Show the user the exact internal note text before running. Append:

```python
def test_write():
    drafts = Path("<session scratchpad>/zendesk-drafts")
    draft = draft_comment(
        TICKET,
        "Test note from the zendesk-tickets skill build. Safe to ignore.",
        public=False,
        runner="<user's name>",
        drafts_dir=drafts,
    )
    print("\n", draft.path)
```

Run it, show the printed draft. On the user's "apply", append and run:

```python
def test_apply():
    drafts = Path("<session scratchpad>/zendesk-drafts")
    path = sorted(drafts.glob(f"{TICKET}-*.json"))[-1]
    print(apply(path))
```

Expected: `posted: https://teamschools.zendesk.com/agent/tickets/<id>`, and the
draft file is gone. Ask the user to open the ticket and confirm the internal
note shows with the signature line.

- [ ] **Step 5: Run the macro preview read-only**

Append and run, no apply:

```python
def test_macro_preview():
    drafts = Path("<session scratchpad>/zendesk-drafts")
    draft_macro(TICKET, "Data - Close Out Older Ticket", runner="<user's name>", drafts_dir=drafts)
```

Expected: a PUBLIC draft with `status: <current> -> solved` and the rendered
greeting. Record under `## Verified live` which keys the preview returned and
whether `comment.public` was present. Delete the draft file it wrote.

- [ ] **Step 6: Delete the live test, run the offline suite, lint, commit**

```bash
rm <worktree>/tests/test_zz_zendesk_tickets_live.py
cd <worktree> && uv run pytest tests/zendesk_tickets tests/zendesk_help_articles -q 2>&1 | tail -n 5
cd <worktree> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/zendesk-tickets/references/zendesk-tickets-api.md </dev/null 2>&1 | tail -n 5
git -C <worktree> add -u
git -C <worktree> commit -m "docs(zendesk): record live verification of the tickets skill

Refs #5630

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

Expected: all offline tests pass, lint clean, `git status` shows no throwaway
file.

---

### Task 8: Pull request

**Files:**

- Read: `.github/pull_request_template.md`

- [ ] **Step 1: Push and open the PR**

Push with `git -C <worktree> push`. Open the PR with
`mcp__github__create_pull_request` against `main`, title
`feat(zendesk): ticket research and triage skill on the Ticketing API`, body
from the template with `Closes #5630`, a summary of the seven commits, the
verification steps run in Task 7 (no ticket content), and the footer
`🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

- [ ] **Step 2: Offer CI watch and review handling**

Per the root CLAUDE.md, offer to watch CI and to respond to `claude-review`
findings. On a yes, invoke `pr-ci-review` and arm a Monitor in that turn.
