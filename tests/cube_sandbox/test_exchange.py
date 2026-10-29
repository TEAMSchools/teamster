import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import jwt
import pytest
import yaml
from starlette.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO / "src" / "cube" / "sandbox_exchange" / "server.py"
PERSONAS_PATH = REPO / "src" / "cube" / "sandbox" / "personas.yml"
REGISTERED_APPS_PATH = (
    REPO / "src" / "cube" / "sandbox_exchange" / "registered_apps.yml"
)
ACCESS_JS = REPO / "src" / "cube" / "access.js"
SECRET = "test-secret-not-used-0123456789-abcdef"


def _load_exchange() -> ModuleType:
    sys.modules.pop("cube_sandbox_exchange", None)
    spec = importlib.util.spec_from_file_location("cube_sandbox_exchange", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["cube_sandbox_exchange"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def exchange() -> ModuleType:
    return _load_exchange()


class _Stub:
    def __init__(self, module: ModuleType, error: Exception | None = None):
        self.calls = 0
        self._module = module
        self._error = error

    def __call__(self, request):
        self.calls += 1
        if self._error:
            raise self._error
        return self._module.Builder("builder@apps.teamschools.org", "client_test")


def _client(module: ModuleType, error: Exception | None = None):
    settings = module.Settings(
        secret=SECRET,
        issuer="https://auth.invalid",
        personas_path=PERSONAS_PATH,
        registered_apps_path=REGISTERED_APPS_PATH,
    )
    stub = _Stub(module, error)
    return TestClient(module.create_app(settings, stub)), stub


def _decode(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=["HS256"])


def test_token_path_mints_default_persona(exchange):
    client, _ = _client(exchange)
    response = client.post("/token")
    assert response.status_code == 200
    body = response.json()
    claims = _decode(body["token"])
    assert claims["email"] == "sheryl.swoopes@ktaf-sandbox.invalid"
    assert claims["exp"] - claims["iat"] == 300
    assert set(claims) == {"email", "iat", "exp"}
    assert body["expires_in"] == 300


def test_persona_path_mints_that_persona(exchange):
    client, _ = _client(exchange)
    response = client.post("/as/aja.ogwumike/token")
    assert _decode(response.json()["token"])["email"] == (
        "aja.ogwumike@ktaf-sandbox.invalid"
    )


def test_persona_path_ignores_case_and_trailing_slash(exchange):
    client, _ = _client(exchange)
    response = client.post("/as/Aja.Ogwumike/token/")
    assert response.status_code == 200
    assert _decode(response.json()["token"])["email"] == (
        "aja.ogwumike@ktaf-sandbox.invalid"
    )


def test_unresolvable_persona(exchange):
    client, _ = _client(exchange)
    response = client.post("/as/unresolvable/token")
    assert _decode(response.json()["token"])["email"] == exchange.UNRESOLVABLE_EMAIL


def test_unknown_persona_is_404_naming_personas(exchange):
    client, stub = _client(exchange)
    response = client.post("/as/nobody/token")
    assert response.status_code == 404
    assert "GET /personas" in response.json()["error"]
    assert "nobody" in response.json()["error"]
    assert stub.calls == 0


def test_persona_header_and_body_are_ignored(exchange):
    client, _ = _client(exchange)
    response = client.post(
        "/token?persona=aja.ogwumike",
        headers={"X-Sandbox-Persona": "aja.ogwumike"},
        json={"persona": "aja.ogwumike"},
    )
    assert _decode(response.json()["token"])["email"] == (
        "sheryl.swoopes@ktaf-sandbox.invalid"
    )


def test_get_on_token_is_405_with_guidance(exchange):
    client, _ = _client(exchange)
    response = client.get("/token")
    assert response.status_code == 405
    body = response.json()
    assert set(body) == {"error"}
    assert "Bearer" in body["error"]
    assert "GET /personas" in body["error"]


def test_unknown_route_is_json_404(exchange):
    client, _ = _client(exchange)
    response = client.get("/nope")
    assert response.status_code == 404
    assert set(response.json()) == {"error"}


def test_personas_lists_every_persona_and_unresolvable(exchange):
    client, _ = _client(exchange)
    response = client.get("/personas")
    assert response.status_code == 200
    listed = response.json()["personas"]
    slugs = [p["persona"] for p in listed]
    expected = [
        p["email"].split("@")[0]
        for p in yaml.safe_load(PERSONAS_PATH.read_text())["personas"]
    ]
    assert sorted(slugs) == sorted([*expected, "unresolvable"])
    assert slugs[0] == "sheryl.swoopes"
    assert slugs[-1] == "unresolvable"
    base = str(client.base_url).rstrip("/")
    for p in listed:
        assert p["exchange_url"].startswith(base)
        assert p["exchange_url"].endswith("/token")
        assert p["summary"]


def test_load_personas_rejects_bad_files(exchange, tmp_path):
    def write(name: str, personas: list[dict]) -> Path:
        path = tmp_path / name
        path.write_text(yaml.safe_dump({"personas": personas}))
        return path

    def p(slug: str, summary: bool = True) -> dict:
        d = {"email": f"{slug}@ktaf-sandbox.invalid"}
        if summary:
            d["builder_summary"] = "A summary."
        return d

    cases = {
        "missing_summary": [p("sheryl.swoopes"), p("a.b", summary=False)],
        "duplicate": [p("sheryl.swoopes"), p("a.b"), p("A.B")],
        "unresolvable": [p("sheryl.swoopes"), p("unresolvable")],
        "no_default": [p("a.b")],
    }
    for name, personas in cases.items():
        with pytest.raises(ValueError):
            exchange.load_personas(write(f"{name}.yml", personas))


def test_load_registered_apps(exchange, tmp_path):
    path = tmp_path / "apps.yml"
    path.write_text(yaml.safe_dump({"apps": [{"client_id": "c1", "name": "One"}]}))
    assert exchange.load_registered_apps(path) == {"c1": "One"}
    path.write_text(yaml.safe_dump({"apps": [{"client_id": "c1", "name": "A"}] * 2}))
    with pytest.raises(ValueError):
        exchange.load_registered_apps(path)
    path.write_text(yaml.safe_dump({"apps": [{"client_id": "", "name": "A"}]}))
    with pytest.raises(ValueError):
        exchange.load_registered_apps(path)
    assert exchange.load_registered_apps(REGISTERED_APPS_PATH) == {}


def test_rejected_becomes_status_and_reason(exchange):
    client, _ = _client(exchange, exchange.Rejected(403, "nope"))
    response = client.post("/token")
    assert response.status_code == 403
    assert response.json() == {"error": "nope"}


def test_network_domains_match_access_js(exchange):
    source = ACCESS_JS.read_text()
    match = re.search(r"NETWORK_EMAIL_DOMAINS = new Set\(\[(.*?)\]\)", source, re.S)
    assert match is not None
    domains = frozenset(re.findall(r'"([^"]+)"', match.group(1)))
    assert exchange.NETWORK_EMAIL_DOMAINS == domains


def test_settings_names_every_missing_variable(exchange, monkeypatch):
    monkeypatch.delenv("CUBE_SANDBOX_API_SECRET", raising=False)
    monkeypatch.delenv("AUTHKIT_ISSUER", raising=False)
    with pytest.raises(RuntimeError) as excinfo:
        exchange.settings_from_environment()
    assert "CUBE_SANDBOX_API_SECRET" in str(excinfo.value)
    assert "AUTHKIT_ISSUER" in str(excinfo.value)
