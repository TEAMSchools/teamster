# Cube sandbox token exchange Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Cloud Run service that trades a Builder Brain app's AuthKit session
token for a 5-minute Cube token signed with the sandbox secret, as the persona
the app's `CUBE_EXCHANGE_URL` path names.

**Architecture:** One PEP 723 Python script (Starlette + PyJWT) in
`src/cube/sandbox_exchange/`, built into a container with `personas.yml` and a
committed app allowlist, deployed by a GitHub Actions workflow to
`teamster-cube-sandbox`. Stateless: no store, no cache beyond WorkOS signing
keys.

**Tech Stack:** Python 3.13, Starlette, uvicorn, PyJWT with `cryptography`,
PyYAML, Cloud Run, Artifact Registry, Secret Manager, GitHub Actions with
Workload Identity Federation.

**Spec:** `docs/superpowers/specs/2026-10-29-cube-sandbox-exchange-design.md`

**Branch:** `cristinabaldor/feat/claude-cube-sandbox-build`, PR #5267, in the
worktree
`/workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-sandbox-build`.
The exchange ships with the sandbox it serves.

## Global Constraints

- The only signing secret the service may hold is the sandbox deployment's
  `CUBEJS_API_SECRET`, read from the environment variable
  `CUBE_SANDBOX_API_SECRET`, mounted from Secret Manager secret
  `cube-sandbox-api-secret` in `teamster-cube-sandbox`.
- Minted token: HS256, payload exactly `{"email", "iat", "exp"}`,
  `exp = iat + 300`. No `act_as`.
- Response on success: HTTP 200 `{"token": <jwt>, "expires_in": 300}`. Every
  failure: `{"error": "<plain sentence>"}`.
- The persona comes from the URL path only. Headers, query parameters and the
  body never choose it.
- Default persona slug `sheryl.swoopes`. `unresolvable` maps to
  `unresolvable@ktaf-sandbox.invalid`.
- `NETWORK_EMAIL_DOMAINS` = `apps.teamschools.org`, `kippmiami.org`, kept equal
  to `src/cube/access.js` by a test.
- No AuthKit token and no minted token in any log line.
- Log line per token:
  `{"event": "cube_sandbox_token", "builder", "persona", "client_id"}`.
  Rejections log `status` and `reason` only.
- Cloud Run: service `cube-sandbox-exchange`, project `teamster-cube-sandbox`,
  region `us-central1`, `--min-instances=0`, runtime account
  `cube-sandbox-exchange-runtime@teamster-cube-sandbox.iam.gserviceaccount.com`.
- Tests run offline: they make their own RSA key pair and never call WorkOS.
- Always `uv run`. Tests live in `tests/cube_sandbox/` so the existing
  `cube sandbox contract` workflow runs them.

## Review Focus

1. A builder pastes `CUBE_EXCHANGE_URL` with a trailing slash
   (`.../as/aja.ogwumike/token/`) or mixed case (`/as/Aja.Ogwumike/token`).
   Expect the same persona, not a redirect or a 404. Owner: Task 3.
2. A builder opens the exchange URL in a browser (GET). Expect a 405 whose
   message says to POST with a Bearer token and points to `GET /personas`.
   Owner: Task 3.
3. WorkOS's key endpoint is unreachable. Expect 503 "could not reach WorkOS",
   not a 401 that blames the builder's token. Owner: Task 4.
4. `Authorization: bearer <t>` (lowercase scheme) or a raw token with no scheme.
   Expect the first to work; the second gets a 401 that shows the right form.
   Owner: Task 4.
5. A token issued a few seconds "in the future" by clock skew. Expect it to pass
   (30 seconds of leeway). Owner: Task 4.

---

### Task 1: Confirm the AuthKit session token's shape (gate)

The spec rests on 3 facts from WorkOS's documentation. Confirm them on a real
token before Task 4, the first task that depends on them. Tasks 2 and 3 may run
while the token is pending. If any fact differs, stop and report to the user; do
not adapt the code.

**Files:** none committed. Script in the session scratchpad.

- [ ] **Step 1: Get one token.** The user gets one session access token and its
      client id from any `@workos-inc/authkit-nextjs` app on the KTAF WorkOS
      tenant, saved to a scratchpad file (never pasted into chat or git). An
      expired token is fine: only its shape matters.
- [ ] **Step 2: Decode it without verifying.** A throwaway script
      (`uv run --with pyjwt --with httpx python <scratchpad>/token_shape.py <file>`)
      prints: the header `kid` and `alg`, the `iss` value, whether `client_id`
      is present and equals the app's client id, and whether an `email` claim is
      present (yes/no, never the value).
- [ ] **Step 3: Check the key set.** The same script fetches
      `<iss>/.well-known/openid-configuration`, prints its `issuer` and
      `jwks_uri`, fetches that `jwks_uri`, and prints whether the token's `kid`
      is in it.

Pass (see the spec's _Revision 2026-10-30_): `alg` is `RS256`; `iss` is
`<base>/user_management/<client id>` where `<base>` is `https://api.workos.com`
or the tenant's custom auth domain (record which: Task 6 needs it); the
discovery document's `issuer` equals `iss`; `client_id` is present; `email` is
present; the `kid` is in the discovered key set. Record `iss`, `jwks_uri` and
the client id in the task ledger.

### Task 2: Plain-language persona summaries

**Files:**

- Modify: `src/cube/sandbox/personas.yml` (add `builder_summary` to each of the
  6 personas)
- Modify: `src/teamster/cube_sandbox/personas.py` (`Persona` gains
  `builder_summary: str`, placed after `purpose`)
- Test: `tests/cube_sandbox/test_personas.py`

**Interfaces:**

- Produces: `personas.yml` entries carry `builder_summary`, one sentence, read
  by Task 3's `load_personas`.

- [ ] **Step 1: Write the failing test**

```python
def test_every_persona_has_a_one_sentence_builder_summary() -> None:
    for p in personas.load(PERSONAS_YML):
        assert p.builder_summary.strip(), p.email
        assert "\n" not in p.builder_summary.strip(), p.email
        assert p.builder_summary.strip().endswith("."), p.email
```

- [ ] **Step 2: Run it.**
      `uv run pytest tests/cube_sandbox/test_personas.py -k builder_summary -v`.
      Expected: FAIL, `TypeError` from `Persona(**p)` once the YAML has the key,
      or `AttributeError` before.
- [ ] **Step 3: Add the field and the 6 sentences.** Write each from the _The
      seven identities_ table in `docs/reference/cube-sandbox.md`, for a reader
      who has never seen a scope column. Example for Swoopes: "Sees every
      school's students and every staff record." Fix any other test that builds
      a `Persona(...)` by hand (`tests/cube_sandbox/test_manifest.py` does) by
      passing `builder_summary="x."`.
- [ ] **Step 4: Run** `uv run pytest tests/cube_sandbox -q 2>&1 | tail -n 5`.
      Expected: all pass.
- [ ] **Step 5: Commit**
      `feat(cube): give each sandbox persona a plain-language summary`.

### Task 3: Personas, minting and routing (no sign-in yet)

**Files:**

- Create: `src/cube/sandbox_exchange/server.py` (PEP 723 block: `starlette`,
  `uvicorn`, `pyjwt[crypto]`, `pyyaml`, `requires-python = ">=3.13"`)
- Create: `src/cube/sandbox_exchange/registered_apps.yml` (`apps: []` plus a
  header comment: one entry per Builder Brain app, `client_id` and `name`, no
  person's name or email)
- Test: `tests/cube_sandbox/test_exchange.py`, loading the script with
  `importlib.util.spec_from_file_location` the way
  `tests/cube/test_mcp_server.py::_load_server` does

**Interfaces:**

- Produces, in `server.py`:
  - `NETWORK_EMAIL_DOMAINS: frozenset[str]`,
    `DEFAULT_PERSONA = "sheryl.swoopes"`,
    `UNRESOLVABLE_EMAIL = "unresolvable@ktaf-sandbox.invalid"`,
    `TOKEN_TTL_SECONDS = 300`
  - `@dataclass(frozen=True) class PersonaEntry: slug: str; email: str; summary: str`
  - `load_personas(path: Path) -> dict[str, PersonaEntry]`: keyed by lowercase
    slug (the email's part before `@`), plus `unresolvable` with a fixed summary
    ("Has no staff record, so every query is denied. Use it to test your app's
    unknown-user screen."). Raises `ValueError` on a missing `builder_summary`,
    a duplicate slug, a persona slugged `unresolvable`, or no `sheryl.swoopes`.
  - `load_registered_apps(path: Path) -> dict[str, str]`: `client_id` to `name`.
    Raises `ValueError` on a duplicate or empty `client_id`.
  - `mint_cube_token(persona_email: str, secret: str, now: int) -> str`
  - `@dataclass(frozen=True) class Builder: email: str; client_id: str`
  - `class Rejected(Exception)` with `status: int` and `reason: str`
  - `@dataclass(frozen=True) class Settings: secret: str; issuer: str; personas_path: Path; registered_apps_path: Path`
  - `settings_from_environment() -> Settings`: reads `CUBE_SANDBOX_API_SECRET`,
    `AUTHKIT_ISSUER`, `PERSONAS_PATH` (default `/app/personas.yml`),
    `REGISTERED_APPS_PATH` (default `/app/registered_apps.yml`); raises
    `RuntimeError` naming each missing variable.
  - `create_app(settings: Settings, authenticate: Callable[[Request], Builder]) -> Starlette`
- Consumes: Task 2's `builder_summary`.

Routes (`redirect_slashes=False`; each token route registered with and without a
trailing slash):

| Method, path            | Result                                                                  |
| ----------------------- | ----------------------------------------------------------------------- |
| POST `/token`           | `authenticate(request)`, then mint for `sheryl.swoopes`                 |
| POST `/as/{slug}/token` | Lowercase `slug`; unknown is 404 before `authenticate` runs             |
| GET `/personas`         | `{"personas": [{"persona", "summary", "exchange_url"}]}`, default first |
| other method on token   | 405                                                                     |
| anything else           | 404                                                                     |

`exchange_url` is built from `request.base_url`. 404 and 405 bodies come from an
exception handler so they are JSON. The 405 reason: "Send a POST with the
signed-in person's AuthKit token as `Authorization: Bearer <token>`. To pick a
persona, see GET /personas." The unknown-persona 404 reason names the slug and
points to `GET /personas`. A `Rejected` from `authenticate` becomes its status
and reason.

Startup decision (differs from the spec's 500 row): `main()` calls
`settings_from_environment()`, `load_personas` and `load_registered_apps` and
exits non-zero on any error. Cloud Run then keeps the previous revision serving,
which is safer than a live revision answering 500.

- [ ] **Step 1: Write the failing tests.** `authenticate` is a stub returning
      `Builder("builder@apps.teamschools.org", "client_test")`. Use
      `starlette.testclient.TestClient`. Tests and their assertions:
  - `test_token_path_mints_default_persona`: 200; decoding the token with the
    test secret gives `email == "sheryl.swoopes@ktaf-sandbox.invalid"`,
    `exp - iat == 300`, and no keys besides `email`, `iat`, `exp`;
    `expires_in == 300`.
  - `test_persona_path_mints_that_persona`: `/as/aja.ogwumike/token` gives
    `aja.ogwumike@ktaf-sandbox.invalid`.
  - `test_persona_path_ignores_case_and_trailing_slash`:
    `/as/Aja.Ogwumike/token/` gives the same email.
  - `test_unresolvable_persona`: email is `UNRESOLVABLE_EMAIL`.
  - `test_unknown_persona_is_404_naming_personas`: 404, `"GET /personas"` in
    `error`, and the stub `authenticate` was never called.
  - `test_persona_header_and_body_are_ignored`: POST `/token` with header
    `X-Sandbox-Persona: aja.ogwumike`, query `?persona=aja.ogwumike`, and JSON
    body `{"persona": "aja.ogwumike"}` still mints Swoopes.
  - `test_get_on_token_is_405_with_guidance`: GET `/token`: 405, JSON `error`
    contains `Bearer` and `GET /personas`.
  - `test_personas_lists_every_persona_and_unresolvable`: slugs equal the 6 in
    the real `personas.yml` plus `unresolvable`; first is `sheryl.swoopes`;
    every `exchange_url` starts with the test client's base URL and ends in
    `/token`.
  - `test_load_personas_rejects_bad_files`: 4 `tmp_path` files, one per
    `ValueError` case above.
  - `test_rejected_becomes_status_and_reason`: a stub raising
    `Rejected(403, "nope")` yields 403 `{"error": "nope"}`.
  - `test_network_domains_match_access_js`: regex the `NETWORK_EMAIL_DOMAINS`
    `Set([...])` literal out of `src/cube/access.js`; equal to the constant.
  - `test_settings_names_every_missing_variable`: with both required variables
    unset, the `RuntimeError` text names both.
- [ ] **Step 2: Run**
      `uv run pytest tests/cube_sandbox/test_exchange.py -v 2>&1 | tail -n 20`.
      Expected: FAIL, script not found.
- [ ] **Step 3: Implement** the interfaces above in `server.py`.
- [ ] **Step 4: Run** the same command. Expected: all pass.
- [ ] **Step 5: Commit**
      `feat(cube): add the sandbox token exchange's persona routes`.

### Task 4: AuthKit session-token verification and logging

**Files:**

- Modify: `src/cube/sandbox_exchange/server.py`
- Test: `tests/cube_sandbox/test_exchange.py`

**Interfaces:**

- Consumes: `Builder`, `Rejected`, `NETWORK_EMAIL_DOMAINS`,
  `load_registered_apps`, `create_app` from Task 3.
- Produces:
  - Task 3's `Settings.issuer` and required `AUTHKIT_ISSUER` become
    `Settings.issuer_base` read from optional `AUTHKIT_ISSUER_BASE`, default
    `https://api.workos.com` (trailing slash stripped). Only
    `CUBE_SANDBOX_API_SECRET` stays required; update
    `test_settings_names_every_missing_variable` to match.
  - `expected_issuer(issuer_base: str, client_id: str) -> str`:
    `f"{issuer_base}/user_management/{client_id}"`.
  - `class SessionTokenVerifier`, constructed with
    `(issuer_base: str, registered_apps: dict[str, str], signing_key: Callable[[str, str], Any] | None = None)`.
    `signing_key(client_id, token)` returns the public key. The default, per
    registered client id and lazily: GET
    `<expected_issuer>/.well-known/openid-configuration` once, then one
    `jwt.PyJWKClient(<its jwks_uri>, cache_keys=True, lifespan=3600)`. A failed
    discovery fetch is the same 503 as an unreachable key set. Tests pass their
    own `signing_key`.
  - `SessionTokenVerifier.__call__(request: Request) -> Builder`, so it is the
    `authenticate` argument of `create_app`.
  - `log_event(event: str, **fields: object) -> None`: one JSON line to stdout
    with `severity` (`INFO` or `WARNING`), which Cloud Logging parses.

Checks, in order, each a `Rejected`:

1. No `Authorization` header, or no `Bearer` scheme (case-insensitive): 401 "No
   AuthKit token. Send the signed-in person's AuthKit token as
   `Authorization: Bearer <token>`."
2. Unverified decode fails: 401 "The AuthKit token is not a readable JWT."
3. Unverified `client_id` missing or not in `registered_apps`: 403 "This app
   (client id `<id>`) is not registered with the sandbox. Ask the data team to
   register it." A forged token with an unknown client id lands here, not at
   401; acceptable, since the reply reveals nothing.
4. Fetching keys raises `jwt.PyJWKClientConnectionError`: 503 "Could not reach
   WorkOS to check the sign-in. Try again in a minute."
5. `jwt.decode(..., algorithms=["RS256"], issuer=expected_issuer(issuer_base, client_id), leeway=30, options={"verify_aud": False})`:
   `ExpiredSignatureError` is 401 "The AuthKit token has expired. Get a fresh
   one from the session."; `InvalidIssuerError` is 401 naming the expected
   issuer; any other `PyJWTError` is 401 "The AuthKit token's signature did not
   verify."
6. No `email` claim: 401 "The AuthKit token has no email claim. The WorkOS JWT
   template must add it." Domain (lowercased, after the last `@`) not in
   `NETWORK_EMAIL_DOMAINS`: 403 "Only KTAF staff accounts can use the sandbox."

On success the route logs `cube_sandbox_token` with `builder`, `persona` (the
email), `client_id`. Every `Rejected` logs `cube_sandbox_rejected` with `status`
and `reason`.

- [ ] **Step 1: Write the failing tests.** A module fixture makes an RSA key
      pair (`cryptography`) and signs tokens with `kid="test"`. The
      `signing_key` stub returns the public key, or raises
      `jwt.PyJWKClientConnectionError` for the 503 test. `registered_apps` is
      `{"client_test": "Test app"}`. Tests:
  - `test_valid_session_token_mints`: 200 through the full app.
  - `test_missing_header_is_401`, `test_raw_token_without_scheme_is_401`
    (`error` contains `Bearer`), `test_lowercase_bearer_works`.
  - `test_garbage_token_is_401`, `test_expired_token_is_401` (`error` contains
    `expired`), `test_wrong_issuer_is_401`, `test_wrong_key_is_401` (signed by a
    second key pair).
  - `test_clock_skew_within_30s_passes`: `iat` 20 seconds in the future.
  - `test_unregistered_client_is_403_naming_it`.
  - `test_jwks_unreachable_is_503`.
  - `test_missing_email_is_401`, `test_outside_domain_is_403`,
    `test_domain_check_is_case_insensitive` (`X@Apps.TeamSchools.org`).
  - `test_logs_never_contain_tokens`: run 1 success and 1 rejection with
    `capsys`; the output has no AuthKit token and no minted token; the success
    line parses as JSON with exactly the 4 spec fields plus `severity`; the
    rejection line has `status` and `reason` and no `builder`.
- [ ] **Step 2: Run** the test file. Expected: the new tests FAIL.
- [ ] **Step 3: Implement**, and wire `main()`:
      `create_app(settings, SessionTokenVerifier(settings.issuer_base, apps))`,
      then
      `uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")), proxy_headers=True, forwarded_allow_ips="*")`.
      `proxy_headers` makes `request.base_url` `https://` behind Cloud Run.
- [ ] **Step 4: Run** the test file. Expected: all pass.
- [ ] **Step 5: Contract test.** Add `test_skill_contract`: replay exactly what
      the skill's §5 snippet sends (POST, only `Authorization: Bearer <t>`, no
      body, no `Content-Type`) and read only `json()["token"]`; then assert that
      token works as a raw `Authorization` value by decoding it with the sandbox
      test secret. Run; expected PASS.
- [ ] **Step 6: Commit**
      `feat(cube): verify AuthKit session tokens in the sandbox exchange`.

### Task 5: Container

**Files:**

- Create: `src/cube/sandbox_exchange/Dockerfile`, modelled on
  `src/cube/mcp/Dockerfile`, with build context `src/cube/`. It copies
  `sandbox_exchange/server.py` and `sandbox_exchange/registered_apps.yml` to
  `/app/`, and `sandbox/personas.yml` to `/app/personas.yml`.
- Create: `src/cube/sandbox_exchange/Dockerfile.dockerignore` (BuildKit's
  per-Dockerfile ignore): `*`, then `!` for exactly those 3 files plus the
  Dockerfile, so `node_modules` and the model never enter the context.
- Create: `src/cube/sandbox_exchange/CLAUDE.md`: what the service is; the spec
  path; that the persona is path-only; that only the sandbox secret may be
  mounted; how to register an app (Task 6's doc section).

- [ ] **Step 1: Build.**
      `docker build -t cube-sandbox-exchange:dev -f src/cube/sandbox_exchange/Dockerfile src/cube/ 2>&1 | tail -n 5`.
      Expected: success.
- [ ] **Step 2: Smoke it.** Run the image with a placeholder
      `CUBE_SANDBOX_API_SECRET`, port 8080; `curl -s localhost:8080/personas`
      lists 7 personas; `curl -s -X POST localhost:8080/token` returns 401 JSON.
      Then run it with no secret set: the container exits non-zero and names the
      variable.
- [ ] **Step 3: Commit** `build(cube): containerize the sandbox token exchange`.

### Task 6: Deploy workflow and documentation, including Charlie's runbook

**Files:**

- Create: `.github/workflows/deploy-cube-sandbox-exchange.yaml`, a copy of
  `deploy-cube-mcp.yaml` with these differences:
  - triggers: `push` to `main` on `src/cube/sandbox_exchange/**`,
    `src/cube/sandbox/personas.yml` and the workflow file; plus
    `workflow_dispatch`
  - `GCP_PROJECT_ID: teamster-cube-sandbox`,
    `SERVICE_NAME: cube-sandbox-exchange`,
    `REGISTRY_IMAGE: us-central1-docker.pkg.dev/teamster-cube-sandbox/cube-sandbox-exchange/cube-sandbox-exchange`
  - build `context: src/cube`, `file: src/cube/sandbox_exchange/Dockerfile`
  - deploy with the runtime account from _Global Constraints_,
    `--max-instances=3`, `--memory=256Mi`, `--allow-unauthenticated` (the
    AuthKit check is the gate, as for the MCP server),
    `--set-env-vars=AUTHKIT_ISSUER_BASE=<base>` only if Task 1 found a custom
    auth domain (otherwise omit it and the default applies),
    `--set-secrets=CUBE_SANDBOX_API_SECRET=cube-sandbox-api-secret:latest`
  - same Workload Identity provider line (`vars.GCP_PROJECT_NUMBER`)
- Modify: `docs/reference/cube-sandbox.md`: a new `## Token exchange` section
  after _Emulating a persona_, with 3 subsections:
  - _Picking a persona_: the 2 URL forms, `GET /personas`, and that switching is
    a settings change plus a restart, never a code change.
  - _Registering an app_: add `client_id` and app `name` to
    `src/cube/sandbox_exchange/registered_apps.yml` in a PR; the merge deploys
    it. No person's name or email in that file.
  - _One-time cloud setup_: the runbook below, verbatim.
- Modify: `docs/reference/cube-sandbox-openapi.yml` only if it names an
  exchange; otherwise leave it (the exchange is not Cube's API).

Runbook text (Charlie Bini runs it once, in order, in his own terminal):

```bash
project=teamster-cube-sandbox
region=us-central1
runtime="cube-sandbox-exchange-runtime@${project}.iam.gserviceaccount.com"

# 1. Billing and APIs
gcloud billing projects link "${project}" --billing-account=<billing account id>
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com --project="${project}"

# 2. Image repository
gcloud artifacts repositories create cube-sandbox-exchange \
  --repository-format=docker --location="${region}" --project="${project}"

# 3. Runtime service account
gcloud iam service-accounts create cube-sandbox-exchange-runtime \
  --display-name="Cube sandbox token exchange" --project="${project}"

# 4. The signing secret. Paste the SANDBOX deployment's CUBEJS_API_SECRET
#    (Cube Cloud > petite-dorton > Settings), then press Ctrl-D.
#    NEVER the production deployment's secret.
gcloud secrets create cube-sandbox-api-secret \
  --replication-policy=automatic --project="${project}"
gcloud secrets versions add cube-sandbox-api-secret --data-file=- \
  --project="${project}"
gcloud secrets add-iam-policy-binding cube-sandbox-api-secret \
  --member="serviceAccount:${runtime}" \
  --role=roles/secretmanager.secretAccessor --project="${project}"

# 5. Deploy rights for this repo's GitHub identity. Copy the member that
#    already deploys the Cube MCP server:
gcloud projects get-iam-policy teamster-mcp --flatten=bindings \
  --filter='bindings.role:roles/run.admin' --format='value(bindings.members)'
deployer='<the principalSet:// member printed above>'
for role in roles/run.admin roles/artifactregistry.writer; do
  gcloud projects add-iam-policy-binding "${project}" \
    --member="${deployer}" --role="${role}"
done
gcloud iam service-accounts add-iam-policy-binding "${runtime}" \
  --member="${deployer}" --role=roles/iam.serviceAccountUser \
  --project="${project}"
```

`serviceAccountUser` is granted on the runtime account only, narrower than the
project-wide grant the spec allows.

- [ ] **Step 1: Write** the workflow, the doc section and the runbook.
- [ ] **Step 2: Lint.** From the worktree:
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .github/workflows/deploy-cube-sandbox-exchange.yaml docs/reference/cube-sandbox.md src/cube/sandbox_exchange/CLAUDE.md </dev/null`.
      Expected: no lint findings (formatting is the hook's job).
- [ ] **Step 3: Build the docs.**
      `uv run mkdocs build --strict 2>&1 | tail -n 5`. Expected: no warnings
      from `cube-sandbox.md`.
- [ ] **Step 4: Commit**
      `ci(cube): deploy the sandbox token exchange to teamster-cube-sandbox`.
- [ ] **Step 5: Push, and add the exchange to PR #5267's body.** Hand the
      runbook to the user to pass to Charlie. Charlie's setup must finish before
      #5267 merges: the merge triggers the deploy workflow.

### Task 7: First deploy and live verification

Blocked until Charlie confirms all 5 runbook steps.

**Files:**

- Modify: `src/cube/sandbox_exchange/registered_apps.yml` (first entry: Task 1's
  client id and its app's name)

- [ ] **Step 1: Register the test app.** Add the entry, commit
      `feat(cube): register the first Builder Brain app with the sandbox exchange`,
      push.
- [ ] **Step 2: Deploy from the branch.** The user runs the workflow from the
      Actions tab with `workflow_dispatch` on this branch (the Codespace token
      cannot dispatch workflows). Expected: green; record the service URL.
- [ ] **Step 3: Exchange live.** With a fresh session token from the test app,
      POST `<url>/token`. Expected: 200 with a token.
- [ ] **Step 4: Query as 3 personas.** POST that token's `token` to the sandbox
      `.../cubejs-api/v1/load` with a `staff_directory` count. Expected: rows
      for `/token` (Swoopes); fewer rows for `/as/ororo.munroe/token`; Cube's
      HTTP 500 `You requested hidden member` for `/as/aja.ogwumike/token`.
- [ ] **Step 5: Prove the secret is not production's.** Send a minted token to
      the production deployment's `/load`. Expected: 403 from `checkAuth`
      (signature invalid). Any 200 means the wrong secret is mounted: stop, tell
      the user, and have Charlie disable the secret version.
- [ ] **Step 6: Check the log.** In Cloud Logging for `cube-sandbox-exchange`,
      the `cube_sandbox_token` lines show `builder`, `persona`, `client_id`, and
      no token.
- [ ] **Step 7: Report** to the user and comment the result on #5523. No builder
      email in the comment.
