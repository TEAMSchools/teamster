"""Research and triage Zendesk tickets through the Ticketing API.

Runs only under pytest: the session fixture in tests/conftest.py loads
ZENDESK_SUBDOMAIN, ZENDESK_EMAIL and ZENDESK_TOKEN from 1Password. See
.claude/skills/zendesk-tickets/SKILL.md for the flow and
references/zendesk-tickets-api.md for the endpoints.
"""

from __future__ import annotations

import os
import re

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
    {
        "status",
        "priority",
        "type",
        "assignee_id",
        "group_id",
        "tags",
        "custom_fields",
        "comment",
        "email_ccs",
    }
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
        response = self.session.request(
            method, self.base + path, timeout=TIMEOUT_SECONDS, **kwargs
        )
        if response.status_code >= 400:
            raise TicketError(
                f"{method} {path} returned {response.status_code}: {response.text[:500]}"
            )
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
        return self._call(
            "GET", f"/tickets/{ticket_id}.json", params={"include": "users,groups"}
        )

    def comments(self, ticket_id: int) -> tuple[list[dict], list[dict]]:
        params = {"page[size]": PAGE_SIZE, "include": "users"}
        comments: list[dict] = []
        users: list[dict] = []
        while True:
            data = self._call(
                "GET", f"/tickets/{ticket_id}/comments.json", params=params
            )
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

    def search(
        self, query: str, sort_by: str = "created_at", sort_order: str = "desc"
    ) -> list[dict]:
        params = {
            "query": query,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "per_page": PAGE_SIZE,
        }
        return self._call("GET", "/search.json", params=params)["results"]

    def ticket_field(self, field_id: int) -> dict:
        return self._call("GET", f"/ticket_fields/{field_id}.json")["ticket_field"]

    def groups(self) -> list[dict]:
        return self._list_all("/groups.json", "groups")

    def group_memberships(self, group_id: int) -> list[dict]:
        return self._list_all(
            f"/groups/{group_id}/memberships.json", "group_memberships"
        )

    def users_show_many(self, ids: list[int]) -> list[dict]:
        joined = ",".join(str(i) for i in ids)
        return self._call("GET", "/users/show_many.json", params={"ids": joined})[
            "users"
        ]

    def macros(self) -> list[dict]:
        return self._list_all("/macros.json", "macros", params={"active": "true"})

    def macro_preview(self, ticket_id: int, macro_id: int) -> dict:
        return self._call("GET", f"/tickets/{ticket_id}/macros/{macro_id}/apply.json")[
            "result"
        ]["ticket"]

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
    return ZendeskTickets(
        values["ZENDESK_SUBDOMAIN"], values["ZENDESK_EMAIL"], values["ZENDESK_TOKEN"]
    )
