"""Research Zendesk tickets through the Ticketing API and draft triage to paste.

Read-only: every call is a GET, and each draft prints for the user to paste into
Zendesk themselves. Runs only under pytest: the session fixture in tests/conftest.py loads
ZENDESK_SUBDOMAIN, ZENDESK_EMAIL and ZENDESK_TOKEN from 1Password. See
.claude/skills/zendesk-tickets/SKILL.md for the flow and
references/zendesk-tickets-api.md for the endpoints.
"""

from __future__ import annotations

import html as html_module
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import requests

TIMEOUT_SECONDS = 60
PAGE_SIZE = 100
SEARCH_MAX_RESULTS = 1000  # Zendesk's own ceiling on search result offsets
CATEGORY_FIELD_ID = 20721852
DEFAULT_GROUPS = ("Data", "Teaching & Learning")
HISTORY_DAYS = 180
SIMILAR_LIMIT = 10
SIMILAR_KEYWORDS = 3
MACRO_EXACT = frozenset({"Data - Close Out Older Ticket"})
MACRO_PATTERN = re.compile(r"^(Data - )?(Re-)?Assign to ")
# Keys of a macro preview that describe a change to the ticket.
CHANGE_KEYS = frozenset(
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
HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
# An "Assign to" macro hands a ticket over; one that also closes it is not the
# macro the allowlist meant, whatever its title says.
ASSIGN_FORBIDDEN_STATUSES = frozenset({"solved", "closed"})


class TicketError(Exception):
    """A refusal or a failed API call. The message is meant for the user."""


class ZendeskTickets:
    """Thin wrapper over the Ticketing REST API. Every method returns the unwrapped object."""

    def __init__(self, subdomain: str, email: str, token: str, session=None):
        self.subdomain = subdomain
        self.base = f"https://{subdomain}.zendesk.com/api/v2"
        self.session = session or requests.Session()
        self.session.auth = (f"{email}/token", token)

    def _get(self, path: str, **kwargs) -> dict:
        # GET is the only method: the skill reads tickets and never writes them.
        # The user pastes every draft into Zendesk so it posts under their name.
        response = self.session.request(
            "GET", self.base + path, timeout=TIMEOUT_SECONDS, **kwargs
        )
        if response.status_code >= 400:
            raise TicketError(
                f"GET {path} returned {response.status_code}: {response.text[:500]}"
            )
        return response.json()

    def _list_all(self, path: str, key: str, params: dict | None = None) -> list[dict]:
        params = {"page[size]": PAGE_SIZE} | (params or {})
        items: list[dict] = []
        while True:
            data = self._get(path, params=params)
            items.extend(data[key])
            meta = data.get("meta", {})
            if not meta.get("has_more"):
                return items
            params = params | {"page[after]": meta["after_cursor"]}

    def ticket_url(self, ticket_id: int) -> str:
        return f"https://{self.subdomain}.zendesk.com/agent/tickets/{ticket_id}"

    def get_ticket(self, ticket_id: int) -> dict:
        return self._get(
            f"/tickets/{ticket_id}.json", params={"include": "users,groups"}
        )

    def comments(self, ticket_id: int) -> tuple[list[dict], list[dict]]:
        params = {"page[size]": PAGE_SIZE, "include": "users"}
        comments: list[dict] = []
        users: list[dict] = []
        while True:
            data = self._get(f"/tickets/{ticket_id}/comments.json", params=params)
            comments.extend(data["comments"])
            users.extend(data.get("users", []))
            meta = data.get("meta", {})
            if not meta.get("has_more"):
                return comments, users
            params = params | {"page[after]": meta["after_cursor"]}

    def get_user(self, user_id: int) -> dict:
        return self._get(f"/users/{user_id}.json")["user"]

    def get_organization(self, org_id: int) -> dict:
        return self._get(f"/organizations/{org_id}.json")["organization"]

    def search(
        self,
        query: str,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        max_results: int = SEARCH_MAX_RESULTS,
    ) -> list[dict]:
        """Follow `next_page` until the results run out or `max_results` is reached."""
        params = {
            "query": query,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "per_page": max(1, min(PAGE_SIZE, max_results)),
            "page": 1,
        }
        results: list[dict] = []
        while True:
            data = self._get("/search.json", params=params)
            results.extend(data["results"])
            if not data.get("next_page") or len(results) >= max_results:
                return results[:max_results]
            params = params | {"page": params["page"] + 1}

    def ticket_field(self, field_id: int) -> dict:
        return self._get(f"/ticket_fields/{field_id}.json")["ticket_field"]

    def groups(self) -> list[dict]:
        return self._list_all("/groups.json", "groups")

    def group_memberships(self, group_id: int) -> list[dict]:
        return self._list_all(
            f"/groups/{group_id}/memberships.json", "group_memberships"
        )

    def users_show_many(self, ids: list[int]) -> list[dict]:
        """`show_many` takes at most 100 ids per call; chunk and concatenate."""
        users: list[dict] = []
        for start in range(0, len(ids), PAGE_SIZE):
            joined = ",".join(str(i) for i in ids[start : start + PAGE_SIZE])
            users.extend(
                self._get("/users/show_many.json", params={"ids": joined})["users"]
            )
        return users

    def macros(self) -> list[dict]:
        return self._list_all("/macros.json", "macros", params={"active": "true"})

    def macro_preview(self, ticket_id: int, macro_id: int) -> dict:
        return self._get(f"/tickets/{ticket_id}/macros/{macro_id}/apply.json")[
            "result"
        ]["ticket"]


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
                {"name": o["name"], "value": o["value"]}
                for o in field["custom_field_options"]
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
        if len(by_leaf) > 1:
            raise TicketError(
                f"Category {name!r} matches several options; use the full name: "
                + ", ".join(o["name"] for o in by_leaf)
            )
        names = [o["name"] for o in options]
        raise TicketError(
            f"No Category option named {name!r}. Closest: "
            + ", ".join(_closest(names, name))
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
        wanted = name.strip().lower()
        for group in self._groups:
            if group["name"].lower() == wanted:
                return group
        raise TicketError(
            f"No group named {name!r}. Available: "
            + ", ".join(sorted(g["name"] for g in self._groups))
        )

    def group_members(self, group_id: int) -> list[dict]:
        if group_id not in self._members:
            ids = [m["user_id"] for m in self.client.group_memberships(group_id)]
            self._members[group_id] = self.client.users_show_many(ids) if ids else []
        return self._members[group_id]

    def resolve_assignee(self, name: str, group_id: int) -> dict:
        wanted = name.strip().lower()
        if not wanted:
            raise TicketError("Assignee name is empty.")
        members = self.group_members(group_id)
        hits = []
        for u in members:
            full = (u.get("name") or "").strip().lower()
            candidates = {
                full,
                (full.split() or [""])[0],
                (u.get("email") or "").lower(),
            }
            candidates.discard("")
            if wanted in candidates:
                hits.append(u)
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise TicketError(
                f"Assignee {name!r} matches several members: "
                + ", ".join(u["name"] for u in hits)
            )
        raise TicketError(
            f"No member of group {group_id} named {name!r}. Members: "
            + ", ".join(sorted(u["name"] for u in members))
        )

    def resolve_macro(self, title: str) -> dict:
        if not macro_allowed(title):
            raise TicketError(
                f"Macro {title!r} is outside the allowlist: 'Data - Close Out Older "
                "Ticket' or a title starting 'Assign to ', 'Data - Assign to ', or "
                "'Data - Re-Assign to '."
            )
        if self._macros is None:
            self._macros = self.client.macros()
        for macro in self._macros:
            if macro["title"] == title:
                return macro
        raise TicketError(f"No active macro titled {title!r}.")


STOPWORDS = frozenset(
    "a an and are as at be but by for from has have how i in is it its my not of on "
    "or our please that the their there this to was we what when where who will with "
    "you your re fw fwd".split()
)


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def age_days(value: str) -> int:
    return (datetime.now(UTC) - parse_ts(value)).days


def keywords(subject: str | None) -> list[str]:
    words = re.findall(r"[a-z0-9]+", (subject or "").lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1][:6]


def format_rows(rows: list[dict], columns: list[str]) -> str:
    cells = [
        [str(r.get(c, "") if r.get(c) is not None else "") for c in columns]
        for r in rows
    ]
    widths = [
        max(len(c), *(len(row[i]) for row in cells)) if cells else len(c)
        for i, c in enumerate(columns)
    ]

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


def format_header(
    ticket: dict, catalog: Catalog, users: list[dict], groups: list[dict]
) -> str:
    group = next((g["name"] for g in groups if g["id"] == ticket.get("group_id")), "")
    category = catalog.category_name(ticket_custom_value(ticket, CATEGORY_FIELD_ID))
    return "\n".join(
        [
            f"#{ticket['id']}  {ticket['subject']}",
            f"status: {ticket['status']}   group: {group}   "
            f"assignee: {_name(users, ticket.get('assignee_id'))}",
            f"requester: {_name(users, ticket.get('requester_id'))}",
            f"category: {category}",
            f"created: {ticket['created_at']}   updated: {ticket['updated_at']}",
        ]
    )


def format_thread(comments: list[dict], users: list[dict]) -> str:
    blocks = []
    for comment in comments:
        kind = "PUBLIC" if comment.get("public") else "INTERNAL"
        author = _name(users, comment.get("author_id"))
        head = f"--- {author}  {kind}  {comment['created_at']}"
        body = (comment.get("plain_body") or comment.get("body") or "").strip()
        files = ", ".join(a["file_name"] for a in comment.get("attachments", []))
        lines = [head, body] + ([f"attachments: {files}"] if files else [])
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _tickets_only(results: list[dict]) -> list[dict]:
    return [r for r in results if r.get("result_type") == "ticket"]


def _group_terms(catalog: Catalog, groups) -> str:
    if isinstance(groups, str):
        groups = [groups]
    return " ".join(f"group_id:{catalog.resolve_group(g)['id']}" for g in groups)


def _client(client: ZendeskTickets | None) -> ZendeskTickets:
    return client or client_from_environment()


def research(ticket_id: int, *, client: ZendeskTickets | None = None) -> dict:
    """Ticket, thread, requester, requester history, and similar tickets in one report."""
    ticket_id = int(ticket_id)
    client = _client(client)
    catalog = Catalog(client)
    data = client.get_ticket(ticket_id)
    ticket, users, groups = (
        data["ticket"],
        data.get("users", []),
        data.get("groups", []),
    )
    comments, comment_users = client.comments(ticket_id)
    known = {u["id"] for u in users}
    users = users + [u for u in comment_users if u["id"] not in known]

    requester = client.get_user(ticket["requester_id"])
    organization = (
        client.get_organization(requester["organization_id"])
        if requester.get("organization_id")
        else None
    )
    since = (datetime.now(UTC) - timedelta(days=HISTORY_DAYS)).strftime("%Y-%m-%d")
    history_query = f"type:ticket requester:{requester['id']} created>{since}"
    history = [
        t for t in _tickets_only(client.search(history_query)) if t["id"] != ticket_id
    ]

    category_value = ticket_custom_value(ticket, CATEGORY_FIELD_ID)
    similar_by_category: list[dict] = []
    if category_value:
        query = (
            f"type:ticket custom_field_{CATEGORY_FIELD_ID}:{category_value} "
            f"{_group_terms(catalog, DEFAULT_GROUPS)}"
        )
        # One page is plenty for a "did we see this before" table; a common
        # Category matches thousands of tickets (seen live 2026-09-30).
        results = client.search(query, max_results=SIMILAR_LIMIT + 1)
        similar_by_category = [
            t for t in _tickets_only(results) if t["id"] != ticket_id
        ][:SIMILAR_LIMIT]
    # Zendesk ANDs bare terms. Live counts on 2026-09-30: all 4-6 subject words
    # matched 1-9 tickets (often only the ticket itself); 3 words matched 1-161.
    words = keywords(ticket["subject"])[:SIMILAR_KEYWORDS]
    similar_by_keywords: list[dict] = []
    if words:
        results = client.search(
            "type:ticket " + " ".join(words), max_results=SIMILAR_LIMIT + 1
        )
        similar_by_keywords = [
            t for t in _tickets_only(results) if t["id"] != ticket_id
        ][:SIMILAR_LIMIT]

    columns = ["id", "status", "subject", "created_at"]
    print(format_header(ticket, catalog, users, groups))
    print(
        f"organization: {organization['name']}"
        if organization
        else "organization: none"
    )
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
    ticket_id = int(ticket_id)
    client = _client(client)
    data = client.get_ticket(ticket_id)
    comments, users = client.comments(ticket_id)
    users = data.get("users", []) + users
    print(f"#{ticket_id}  {data['ticket']['subject']}\n")
    print(format_thread(comments, users))
    return comments


def search(
    query: str, groups=None, *, client: ZendeskTickets | None = None
) -> list[dict]:
    client = _client(client)
    catalog = Catalog(client)
    full = "type:ticket " + query
    if groups:
        full += " " + _group_terms(catalog, groups)
    results = _tickets_only(client.search(full))
    columns = ["id", "status", "subject", "requester_id", "created_at", "updated_at"]
    print(format_rows(results, columns))
    return results


def queue(groups=DEFAULT_GROUPS, *, client: ZendeskTickets | None = None) -> list[dict]:
    """Unsolved tickets in the named groups, oldest first."""
    client = _client(client)
    catalog = Catalog(client)
    query = f"type:ticket status<solved {_group_terms(catalog, groups)}"
    results = _tickets_only(
        client.search(query, sort_by="created_at", sort_order="asc")
    )
    ids: list[int] = sorted(
        {int(t["assignee_id"]) for t in results if t.get("assignee_id")}
        | {int(t["requester_id"]) for t in results if t.get("requester_id")}
    )
    users = client.users_show_many(ids) if ids else []
    rows = [
        {
            "id": t["id"],
            "status": t["status"],
            "age": age_days(t["created_at"]),
            "requester": _name(users, t.get("requester_id")),
            "subject": t["subject"],
            "category": catalog.category_name(
                ticket_custom_value(t, CATEGORY_FIELD_ID)
            ),
            "assignee": _name(users, t.get("assignee_id")),
        }
        for t in results
    ]
    columns = ["id", "status", "age", "requester", "subject", "category", "assignee"]
    print(format_rows(rows, columns))
    return rows


NOTICE = (
    "To send this, paste it into the ticket in Zendesk yourself so it posts under "
    "your name, and make any field changes listed above. This skill is read-only "
    "and cannot post to Zendesk."
)


@dataclass
class Draft:
    ticket_id: int
    subject: str
    payload: dict
    display: str


def _changes(ticket: dict, new: dict, catalog: Catalog, users: list[dict]) -> list[str]:
    lines = []
    for key in ("status", "priority", "type", "group_id"):
        if key in new and new[key] != ticket.get(key):
            lines.append(f"{key}: {ticket.get(key) or ''} -> {new[key]}")
    if "assignee_id" in new and new["assignee_id"] != ticket.get("assignee_id"):
        old = _name(users, ticket.get("assignee_id"))
        lines.append(f"assignee: {old} -> {_name(users, new['assignee_id'])}")
    for field in new.get("custom_fields", []):
        old_value = ticket_custom_value(ticket, field["id"])
        new_value = field.get("value")
        if new_value == old_value:
            continue
        if field["id"] == CATEGORY_FIELD_ID:
            lines.append(
                f"category: {catalog.category_name(old_value)} -> "
                f"{catalog.category_name(new_value)}"
            )
        else:
            lines.append(
                f"custom_field {field['id']}: {old_value or ''} -> {new_value}"
            )
    if "tags" in new and new["tags"] != ticket.get("tags"):
        lines.append(f"tags: {ticket.get('tags')} -> {new['tags']}")
    if new.get("email_ccs"):
        lines.append(f"email_ccs: {new['email_ccs']}")
    return lines


def _html_to_text(html: str) -> str:
    """Block tags become newlines, other tags vanish; for the draft display only."""
    text = re.sub(r"</(p|div|li|h\d)>|<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = HTML_TAG_RE.sub("", text)
    text = html_module.unescape(text).replace("\xa0", " ")
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def _show_draft(
    ticket: dict, payload: dict, catalog: Catalog, users: list[dict]
) -> Draft:
    comment = payload["ticket"].get("comment")
    if comment is None:
        kind = "none"
    else:
        kind = "PUBLIC" if comment.get("public") else "INTERNAL"
    display_lines = [
        f"DRAFT for #{ticket['id']}  {ticket['subject']}",
        f"comment: {kind}",
    ]
    if comment:
        text = comment.get("body") or _html_to_text(comment.get("html_body", ""))
        display_lines += ["", text, ""]
    display_lines += _changes(ticket, payload["ticket"], catalog, users) or [
        "no field changes"
    ]
    if payload["ticket"].get("status") in ASSIGN_FORBIDDEN_STATUSES:
        display_lines.append(
            "note: solving reaches the requester (Zendesk emails them), even with "
            "an internal comment"
        )
    display_lines += ["", NOTICE]
    display = "\n".join(display_lines)
    print(display)
    return Draft(ticket["id"], ticket["subject"], payload, display)


def draft_comment(
    ticket_id: int,
    body: str,
    *,
    public: bool,
    runner: str | None = None,
    status: str | None = None,
    assignee: str | None = None,
    category: str | None = None,
    client: ZendeskTickets | None = None,
) -> Draft:
    """Print a reply or note and its field changes for the user to paste."""
    if public is not True and public is not False:
        # The PUBLIC / INTERNAL label tells the user where to paste the text, so
        # it comes only from an explicit answer, never from `None` or "no".
        raise TicketError("`public` must be True or False, nothing else.")
    ticket_id = int(ticket_id)
    client = _client(client)
    catalog = Catalog(client)
    data = client.get_ticket(ticket_id)
    ticket, users = data["ticket"], data.get("users", [])

    if not public:
        if not runner:
            raise TicketError(
                "An internal note needs `runner=<your name>` for its signature line."
            )
        body = f"{body.rstrip()}\n\n{SIGNATURE.format(runner=runner)}"
    update: dict = {"comment": {"body": body, "public": public}}
    if status:
        update["status"] = status
    if assignee:
        if not ticket.get("group_id"):
            raise TicketError(
                f"Ticket #{ticket_id} has no group, so there is no member list to "
                "resolve an assignee against. Set the group in Zendesk first."
            )
        member = catalog.resolve_assignee(assignee, ticket["group_id"])
        update["assignee_id"] = member["id"]
        users = users + [member]
    if category:
        value = catalog.resolve_category(category)["value"]
        update["custom_fields"] = [{"id": CATEGORY_FIELD_ID, "value": value}]
    return _show_draft(ticket, {"ticket": update}, catalog, users)


def draft_macro(
    ticket_id: int,
    macro_title: str,
    *,
    runner: str,
    client: ZendeskTickets | None = None,
) -> Draft:
    """Preview an allowlisted macro and print its rendered result as a draft."""
    ticket_id = int(ticket_id)
    client = _client(client)
    catalog = Catalog(client)
    macro = catalog.resolve_macro(macro_title)
    data = client.get_ticket(ticket_id)
    ticket, users = data["ticket"], data.get("users", [])
    preview = client.macro_preview(ticket_id, macro["id"])
    # The preview is the whole ticket with the macro applied. Keep only what the
    # macro changed, so unchanged tags, ccs and fields are not listed as changes.
    update = {
        k: v
        for k, v in preview.items()
        if k in CHANGE_KEYS
        and (k == "comment" or (v != ticket.get(k) and (v or ticket.get(k))))
    }
    if (
        macro_title not in MACRO_EXACT
        and update.get("status") in ASSIGN_FORBIDDEN_STATUSES
    ):
        raise TicketError(
            f"Macro {macro_title!r} would set status to {update['status']!r}. An "
            "'Assign to' macro hands a ticket over; one that closes it is refused."
        )
    comment = update.get("comment")
    if not comment:
        update.pop("comment", None)
    if comment:
        text = comment.get("body") or comment.get("html_body", "")
        public = bool(comment.get("public", True))
        signature = SIGNATURE.format(runner=runner)
        if HTML_TAG_RE.search(text):
            # The preview renders the macro's rich text as HTML (seen live
            # 2026-09-30). The display strips the tags so the user pastes text.
            if not public:
                text += f"<p>{signature}</p>"
            update["comment"] = {"html_body": text, "public": public}
        else:
            if not public:
                text += f"\n\n{signature}"
            update["comment"] = {"body": text, "public": public}
    if update.get("assignee_id"):
        users = users + client.users_show_many([update["assignee_id"]])
    return _show_draft(ticket, {"ticket": update}, catalog, users)
