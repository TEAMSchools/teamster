"""Minimal Cube REST client: compiled SQL, rows, and the refusals that keep a
validation run honest. Stdlib only; auth mirrors `src/cube/mcp/server.py`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

TIMEOUT_SECONDS = 60
_FACT = re.compile(r"kipptaf_marts`?\.`?(fct_\w+)", re.IGNORECASE)
_STR = r"'(?:\\.|[^'\\])*'"
_STRING = re.compile(_STR)
_LIST = rf"{_STR}(?:\s*,\s*{_STR})*"
_SCHOOLS = re.compile(
    r"(?<!\w)abbreviation`?\s*(?:"
    rf"IN\s*UNNEST\s*\(\s*\[\s*(?:{_LIST})?\s*\]\s*\)"
    rf"|IN\s*\(\s*{_LIST}\s*\)"
    rf"|=\s*{_STR}"
    r")",
    re.IGNORECASE,
)
_DENY = re.compile(r"\b1\s*=\s*0\b")
_LIMIT = re.compile(r"\s+LIMIT\s+\d+\s*;?\s*\Z", re.IGNORECASE)


class CubeRefusal(RuntimeError):
    """The compiled query would not reproduce the view's real behavior."""


class CubeError(RuntimeError):
    """Cube answered with an HTTP error, a compile error, or timed out."""


class _Rows(Protocol):
    def rows(self, sql: str) -> list[dict]: ...


@dataclass(frozen=True)
class Compiled:
    sql: str
    params: list
    pre_aggregations: list


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def mint_token(secret: str, email: str, now: int, ttl: int = 300) -> str:
    """Sign an HS256 JWT whose whole payload is Cube's security context.

    Cube's `checkAuth` needs `iat` for its `maxAge` check, so the payload is
    exactly `email`, `iat` and `exp`.
    """
    header = _b64(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
    )
    payload = _b64(
        json.dumps(
            {"email": email, "iat": now, "exp": now + ttl}, separators=(",", ":")
        ).encode()
    )
    sig = hmac.new(
        secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256
    ).digest()

    return f"{header}.{payload}.{_b64(sig)}"


def urlopen_json(
    method: str, url: str, headers: dict[str, str], body: dict | None = None
) -> Any:
    """Send one request and return the parsed JSON body."""
    if urllib.parse.urlparse(url).scheme != "https":
        raise CubeError(f"Cube URL must be https; got {url!r}")

    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    if data is not None:
        req.add_header("Content-Type", "application/json")

    try:
        # trunk-ignore(bandit/B310): scheme checked to be https above
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise CubeError(f"Cube {method} {e.code}: {e.read().decode()[:500]}") from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise CubeError(f"Cube {method} did not answer: {e}") from None


class Cube:
    """Cube REST client acting as `email`."""

    def __init__(
        self,
        base_url: str,
        secret: str,
        email: str,
        fetch: Callable[..., Any] = urlopen_json,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if urllib.parse.urlparse(base_url).scheme != "https":
            raise CubeError(f"Cube base URL must be https; got {base_url!r}")

        self._base = base_url.rstrip("/")
        self._secret = secret
        self._email = email
        self._fetch = fetch
        self._sleep = sleep
        self._clock = clock

    def _call(self, method: str, path: str, body: dict | None = None) -> Any:
        deadline = self._clock() + TIMEOUT_SECONDS

        while True:
            headers = {
                "Authorization": mint_token(
                    self._secret, self._email, int(self._clock())
                )
            }
            out = self._fetch(method, f"{self._base}{path}", headers, body)

            if not (isinstance(out, dict) and out.get("error") == "Continue wait"):
                return out

            if self._clock() >= deadline:
                raise CubeError(f"Cube {method} {path} still waiting after 60s")

            self._sleep(1)

    def compiled(self, query: dict) -> Compiled:
        """Return the SQL Cube would run for `query`, as this viewer.

        Raises:
            CubeError: Cube could not compile the query.
        """
        q = urllib.parse.quote(json.dumps(_utc(query)))
        out = self._call("GET", f"/sql?query={q}")
        sql = out["sql"]

        if sql.get("error"):
            raise CubeError(f"Cube GET /sql: {sql['error']}")

        text, params = sql["sql"]

        return Compiled(text, list(params), list(sql.get("preAggregations") or []))

    def load(self, query: dict) -> list[dict]:
        """Run `query` and return its rows."""
        out = self._call("POST", "/load", {"query": _utc(query)})

        return out["data"]

    def meta(self) -> dict:
        """Return Cube's `/meta` response: every cube and view this viewer sees."""
        return self._call("GET", "/meta")


@dataclass(frozen=True)
class MemberDoc:
    """What a member tells a caller about itself through `/meta`."""

    name: str
    title: str
    description: str
    ai_context: str
    kind: str  # measure, dimension or segment


_KINDS = {"measures": "measure", "dimensions": "dimension", "segments": "segment"}


def member_docs(meta: dict, view: str) -> dict[str, MemberDoc]:
    """Return `view`'s members from a `/meta` response, keyed by bare name."""
    docs: dict[str, MemberDoc] = {}

    for cube in meta.get("cubes", []):
        if cube.get("name") != view:
            continue

        for field, kind in _KINDS.items():
            for m in cube.get(field) or []:
                name = m["name"].split(".", 1)[-1]
                docs[name] = MemberDoc(
                    name=name,
                    title=m.get("title") or "",
                    description=m.get("description") or "",
                    ai_context=(m.get("meta") or {}).get("ai_context") or "",
                    kind=kind,
                )

    return docs


def _utc(query: dict) -> dict:
    """Default the query timezone to UTC, as `src/cube/mcp/server.py` does.

    Mart dates are midnight UTC; the deployment's default zone would shift a
    date dimension to the previous evening and its DATE to the previous day.
    """
    return query if query.get("timezone") else {**query, "timezone": "UTC"}


_ESCAPES = {"\\": "\\\\", "'": "\\'", "\n": "\\n", "\r": "\\r", "\t": "\\t"}


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"

    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"

    if isinstance(value, (int, float)):
        return str(value)

    if isinstance(value, str):
        return "'" + "".join(_ESCAPES.get(c, c) for c in value) + "'"

    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_literal(v) for v in value) + "]"

    raise CubeError(f"Unsupported parameter type {type(value).__name__}")


def _split(sql: str) -> list[tuple[bool, str]]:
    """Split `sql` into (is_string_literal, text) pieces."""
    out: list[tuple[bool, str]] = []
    pos = 0

    for m in _STRING.finditer(sql):
        out.append((False, sql[pos : m.start()]))
        out.append((True, m.group()))
        pos = m.end()

    out.append((False, sql[pos:]))

    return out


def bind(compiled: Compiled) -> str:
    """Inline each `?` with its parameter as a BigQuery literal.

    A `?` inside a quoted string literal is text, not a placeholder.

    Raises:
        CubeError: placeholder and parameter counts differ, or a parameter has
            no BigQuery literal form.
    """
    pieces = _split(compiled.sql)
    holes = sum(t.count("?") for lit, t in pieces if not lit)

    if holes != len(compiled.params):
        raise CubeError(
            f"SQL has {holes} placeholders but {len(compiled.params)} parameters"
        )

    params = iter(compiled.params)

    return "".join(
        t if lit else re.sub(r"\?", lambda _: _literal(next(params)), t)
        for lit, t in pieces
    )


def drop_limit(sql: str) -> str:
    """Remove a trailing `LIMIT <n>`."""
    return _LIMIT.sub("", sql)


def _unquote(literal: str) -> str:
    return re.sub(r"\\(.)", r"\1", literal[1:-1])


def _school_filters(bound: str) -> list[set[str]]:
    """Return the abbreviation set of each school filter in the SQL."""
    return [
        {_unquote(s) for s in _STRING.findall(m.group(0))}
        for m in _SCHOOLS.finditer(bound)
    ]


def sort_school_filters(sql: str) -> str:
    """Sort the abbreviations inside each school filter of bound SQL.

    The list comes from `dim_locations` with no order, so a fingerprint taken
    over the raw SQL would move whenever the list's order did.
    """

    def ordered(m: re.Match) -> str:
        literals = iter(sorted(_STRING.findall(m.group(0))))
        return _STRING.sub(lambda _: next(literals), m.group(0))

    return _SCHOOLS.sub(ordered, sql)


def refuse_unless_safe(
    compiled: Compiled, *, view_fact: str, network_schools: set[str]
) -> None:
    """Refuse a compiled query that would not match a raw rebuild.

    Raises:
        CubeRefusal: a pre-aggregation answered it, it reads a fact other than
            `view_fact`, or its school filter is missing, a
            default-deny, or not exactly `network_schools`.
    """
    if compiled.pre_aggregations:
        raise CubeRefusal(
            "Cube served this from a pre-aggregation, which is stored data "
            "rather than the fact the view reads."
        )

    facts = {m.lower() for m in _FACT.findall(compiled.sql)}
    others = facts - {view_fact.rsplit(".", 1)[-1].lower()}

    if others:
        raise CubeRefusal(f"SQL reads facts other than {view_fact}: {sorted(others)}")

    bound = bind(compiled)
    code = "".join(t for lit, t in _split(bound) if not lit)

    if _DENY.search(code):
        raise CubeRefusal("SQL carries a `1 = 0` default-deny predicate.")

    filters = _school_filters(bound)

    if not filters:
        raise CubeRefusal(
            "No school filter found in the SQL, so the viewer's scope cannot be "
            "confirmed as the whole network."
        )

    for schools in filters:
        if schools != network_schools:
            raise CubeRefusal(
                f"School filter covers {len(schools)} of {len(network_schools)} "
                "network schools; the viewer is not network scope."
            )


def network_schools(wh: _Rows) -> set[str]:
    """Return every school abbreviation the `network` scope enumerates.

    Mirrors `loadUniverses` in `src/cube/cube.js` fed through the `network`
    case of `computeAllowedAbbreviations` in `src/cube/access.js`.
    """
    rows = wh.rows("SELECT abbreviation FROM `kipptaf_marts.dim_locations`")

    return {r["abbreviation"] for r in rows if r["abbreviation"] is not None}
