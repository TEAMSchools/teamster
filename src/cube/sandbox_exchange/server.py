#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "starlette",
#   "uvicorn",
#   "pyjwt[crypto]",
#   "pyyaml",
# ]
# ///
"""Token exchange for the Cube sandbox deployment.

A Builder Brain app POSTs a signed-in person's AuthKit token and gets back a
short-lived Cube token, signed with the SANDBOX deployment's secret, for the
fabricated persona the URL path names. The sandbox secret verifies only against
synthetic data, so the token never reaches production Cube.

Runs standalone in a container: it parses personas.yml itself and must not
import the `teamster` package. Sign-in verification is injected as
`authenticate`; `main()` is the seam where the real verifier is wired in.
"""

import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import jwt
import yaml
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

# Must equal NETWORK_EMAIL_DOMAINS in src/cube/access.js; a test compares them.
NETWORK_EMAIL_DOMAINS = frozenset({"apps.teamschools.org", "kippmiami.org"})
DEFAULT_PERSONA = "sheryl.swoopes"
UNRESOLVABLE_SLUG = "unresolvable"
UNRESOLVABLE_EMAIL = "unresolvable@ktaf-sandbox.invalid"
UNRESOLVABLE_SUMMARY = (
    "Has no staff record, so every query is denied. Use it to test your app's "
    "unknown-user screen."
)
TOKEN_TTL_SECONDS = 300

METHOD_NOT_ALLOWED_REASON = (
    "Send a POST with the signed-in person's AuthKit token as "
    "`Authorization: Bearer <token>`. To pick a persona, see GET /personas."
)


@dataclass(frozen=True)
class PersonaEntry:
    slug: str
    email: str
    summary: str


@dataclass(frozen=True)
class Builder:
    email: str
    client_id: str


class Rejected(Exception):
    def __init__(self, status: int, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason


@dataclass(frozen=True)
class Settings:
    secret: str
    issuer: str
    personas_path: Path
    registered_apps_path: Path


def settings_from_environment() -> Settings:
    secret = os.environ.get("CUBE_SANDBOX_API_SECRET", "").strip()
    issuer = os.environ.get("AUTHKIT_ISSUER", "").strip()
    missing = [
        name
        for name, value in (
            ("CUBE_SANDBOX_API_SECRET", secret),
            ("AUTHKIT_ISSUER", issuer),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("Missing required variables: " + ", ".join(missing))
    return Settings(
        secret=secret,
        issuer=issuer,
        personas_path=Path(os.environ.get("PERSONAS_PATH", "/app/personas.yml")),
        registered_apps_path=Path(
            os.environ.get("REGISTERED_APPS_PATH", "/app/registered_apps.yml")
        ),
    )


def load_personas(path: Path) -> dict[str, PersonaEntry]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    personas: dict[str, PersonaEntry] = {}
    for entry in raw.get("personas") or []:
        email = entry["email"]
        slug = email.split("@", 1)[0].lower()
        if slug == UNRESOLVABLE_SLUG:
            raise ValueError(f"{path}: persona slug {slug!r} is reserved")
        if slug in personas:
            raise ValueError(f"{path}: duplicate persona slug {slug!r}")
        summary = (entry.get("builder_summary") or "").strip()
        if not summary:
            raise ValueError(f"{path}: persona {email} has no builder_summary")
        personas[slug] = PersonaEntry(slug=slug, email=email, summary=summary)
    if DEFAULT_PERSONA not in personas:
        raise ValueError(f"{path}: default persona {DEFAULT_PERSONA!r} is missing")
    personas[UNRESOLVABLE_SLUG] = PersonaEntry(
        slug=UNRESOLVABLE_SLUG, email=UNRESOLVABLE_EMAIL, summary=UNRESOLVABLE_SUMMARY
    )
    return personas


def load_registered_apps(path: Path) -> dict[str, str]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    apps: dict[str, str] = {}
    for entry in raw.get("apps") or []:
        client_id = str(entry.get("client_id") or "").strip()
        if not client_id:
            raise ValueError(f"{path}: an app has an empty client_id")
        if client_id in apps:
            raise ValueError(f"{path}: duplicate client_id {client_id!r}")
        apps[client_id] = str(entry.get("name") or "")
    return apps


def mint_cube_token(persona_email: str, secret: str, now: int) -> str:
    # `iat` is required: cube.js verifies with maxAge, which reads iat, not exp.
    return jwt.encode(
        {"email": persona_email, "iat": now, "exp": now + TOKEN_TTL_SECONDS},
        secret,
        algorithm="HS256",
    )


def _ordered(personas: dict[str, PersonaEntry]) -> list[PersonaEntry]:
    middle = [
        p
        for slug, p in personas.items()
        if slug not in (DEFAULT_PERSONA, UNRESOLVABLE_SLUG)
    ]
    return [personas[DEFAULT_PERSONA], *middle, personas[UNRESOLVABLE_SLUG]]


def create_app(
    settings: Settings, authenticate: Callable[[Request], Builder]
) -> Starlette:
    personas = load_personas(settings.personas_path)

    def exchange(request: Request) -> JSONResponse:
        slug = request.path_params.get("slug", DEFAULT_PERSONA).lower()
        persona = personas.get(slug)
        if persona is None:
            raise HTTPException(
                404, f"No persona named {slug!r}. See GET /personas for the list."
            )
        authenticate(request)
        token = mint_cube_token(persona.email, settings.secret, int(time.time()))
        return JSONResponse({"token": token, "expires_in": TOKEN_TTL_SECONDS})

    def list_personas(request: Request) -> JSONResponse:
        base = str(request.base_url)
        return JSONResponse(
            {
                "personas": [
                    {
                        "persona": p.slug,
                        "summary": p.summary,
                        "exchange_url": f"{base}as/{p.slug}/token",
                    }
                    for p in _ordered(personas)
                ]
            }
        )

    def http_error(_request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, HTTPException)
        if exc.status_code == 404 and exc.detail == "Not Found":
            reason = "No such route. See GET /personas."
        elif exc.status_code == 405:
            reason = METHOD_NOT_ALLOWED_REASON
        else:
            reason = exc.detail
        return JSONResponse(
            {"error": reason}, status_code=exc.status_code, headers=exc.headers
        )

    def rejected(_request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, Rejected)
        return JSONResponse({"error": exc.reason}, status_code=exc.status)

    post = ["POST"]
    app = Starlette(
        routes=[
            Route("/token", exchange, methods=post),
            Route("/token/", exchange, methods=post),
            Route("/as/{slug}/token", exchange, methods=post),
            Route("/as/{slug}/token/", exchange, methods=post),
            Route("/personas", list_personas, methods=["GET"]),
        ],
        exception_handlers={HTTPException: http_error, Rejected: rejected},
    )
    app.router.redirect_slashes = False
    return app


def main() -> None:
    try:
        settings = settings_from_environment()
        load_personas(settings.personas_path)
        load_registered_apps(settings.registered_apps_path)
    except (RuntimeError, ValueError, OSError) as error:
        # Exiting keeps Cloud Run serving the previous revision.
        print(error, file=sys.stderr)
        sys.exit(1)
    # Task 4: build the AuthKit verifier, `create_app(settings, verifier)`, and
    # run it under uvicorn.


if __name__ == "__main__":
    main()
