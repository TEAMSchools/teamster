# Cube sandbox token exchange — design

Refs #5523. Parent: #5266. Branch:
`cristinabaldor/feat/claude-cube-sandbox-build` (PR #5267).

## Intent

KTAF staff who are new to development will build apps with the Builder Brain,
MasterBorn's Claude Code plugin (`kipptaf/KIPP-AI-Brain-v2`). Its
`cube-integration` skill codes every app to one sign-in path: the person signs
in through WorkOS AuthKit, the app sends that person's AuthKit token to a KTAF
token exchange, and the exchange hands back a short-lived Cube token. The app
then calls Cube's REST API with it. The app never holds a Cube signing secret.

Today that path exists only for production, inside the Cube MCP server. Builders
need it pointed at the sandbox, so they develop against fabricated data with
exactly the code that later runs against production. Switching an app from
sandbox to production must be a change of 2 URLs and nothing else.

## Goals

- A REST token exchange for the sandbox that matches the skill's contract byte
  for byte, so a Builder Brain app works against it unchanged.
- Every signed-in KTAF staff account can use it. The data is fabricated, so a
  wide door costs nothing, and a named allowlist would mean a ticket per
  builder.
- Each signed-in builder sees the sandbox as a fabricated persona, never as
  themselves. The default persona is network-wide, so every screen shows data on
  day one.
- A builder switches persona themselves, by changing `CUBE_EXCHANGE_URL` in
  their app's settings. Building for more than one permission level is part of
  the normal routine, not a request to the data team: every app a builder ships
  will be used by people who see different slices of data.
- One log line per token issued, naming the builder, the persona and the app, so
  the sandbox has the per-app audit trail the production path will need.

## Non-goals

- The production exchange. The code is written so a production mode is
  configuration (see _Left to the builder_), but deploying it waits on privacy
  sign-off and is a separate decision.
- Proxying queries. The skill calls Cube directly with the returned token, so
  the exchange never sees a query.
- Turning Cube's denial (HTTP 500, `You requested hidden member`) into a 403.
  Apps reach Cube directly, so the exchange cannot, and the skill already
  explains the 500.
- An in-app "view as" switcher. That is a Builder Brain feature. The exchange's
  per-persona URLs support one later without a change here.
- Background or unattended tokens. There is no service identity.

## Anti-goals

The design fails, even if it works, if any of these happens:

- The exchange can ever issue a token signed with the production
  `CUBEJS_API_SECRET`.
- A header, query parameter or body field can choose the persona. That would put
  a scope in app code, which the skill forbids, and app code would then differ
  between sandbox and production. The persona lives only in the URL path, which
  the app reads from `CUBE_EXCHANGE_URL` configuration, so the code that runs
  against the sandbox is the code that runs against production.
- A minted Cube token, or the AuthKit token, appears in a log.
- A builder's own email reaches Cube. The sandbox has no row for real staff, so
  that request would fail as an unknown user, which is the confusion the default
  persona exists to remove.

## The contract (decided — from the skill, `skills/cube-integration/SKILL.md` §5)

Request:

```http
POST <CUBE_EXCHANGE_URL>
Authorization: Bearer <AuthKit access token>
```

No body. `CUBE_EXCHANGE_URL` is the full URL the app posts to, path included.
The path picks the persona:

| `CUBE_EXCHANGE_URL` path | Persona                                                   |
| ------------------------ | --------------------------------------------------------- |
| `/token`                 | The default, `sheryl.swoopes` (network-wide)              |
| `/as/<persona>/token`    | `<persona>`, the part of a persona's email before the `@` |

So `https://<exchange host>/as/aja.ogwumike/token` signs the builder in as A'ja
Ogwumike, who resolves but can see nothing. The skill appends nothing to
`CUBE_EXCHANGE_URL`, so the persona path works with the skill as written.

`GET /personas` lists every persona with its `CUBE_EXCHANGE_URL` and a
one-sentence, plain-language description of what it can see, so a builder picks
one without reading `personas.yml`. It needs no sign-in: every persona is
fabricated.

Success, HTTP 200:

```json
{ "token": "<HS256 JWT>", "expires_in": 300 }
```

The skill reads only `token`; `expires_in` is extra and harmless. The app then
sends `Authorization: <token>` to `<CUBE_API_URL>/load`. For the sandbox,
`CUBE_API_URL` is
`https://petite-dorton.gcp-us-central1.cubecloudapp.dev/cubejs-api/v1`, which
ends in `/v1` because the skill appends `/load`.

Failures, each a JSON body `{"error": "<plain sentence>"}`:

| Status | When                                                                                                          |
| ------ | ------------------------------------------------------------------------------------------------------------- |
| 401    | No `Authorization` header, or the AuthKit token fails verification or has expired                             |
| 403    | A valid token from an app not on the allowlist, or whose `email` is not on a KTAF domain; the body says which |
| 404    | `/as/<persona>/token` names no persona; the body points to `GET /personas`                                    |
| 405    | Any method other than `POST` on a token path                                                                  |
| 500    | The exchange is misconfigured (no secret, unreadable `personas.yml`); the body says which                     |

## The minted token (decided)

HS256 over the sandbox deployment's `CUBEJS_API_SECRET`. The whole payload is
Cube's security context, so `email` sits at the top level:

```json
{ "email": "<persona address>", "iat": 1790000000, "exp": 1790000300 }
```

`iat` is required: `checkAuth` rejects a token without one. `exp` is 5 minutes
after `iat`, matching the MCP server's `TOKEN_TTL_SECONDS`. No other claims. In
particular no `act_as`: the exchange resolves the persona itself, so Cube needs
no emulation and `CUBE_IMPERSONATORS` stays unset on the sandbox.

## Verifying the AuthKit token (decided)

A Builder Brain app sends the **session** access token from
`@workos-inc/authkit-nextjs`. That is not the token the MCP server verifies: the
MCP server receives AuthKit Connect (OAuth) tokens, whose issuer is the AuthKit
domain. WorkOS documents session tokens differently
(workos.com/docs/authkit/sessions, /docs/authkit/applications):

- signed RS256, verified against `https://api.workos.com/sso/jwks/<client id>`;
- `iss` is `https://api.workos.com/`, or the custom auth domain if the tenant
  configures one, and is the same for every application in the environment;
- a `client_id` claim names the application the person signed in through.

So the exchange does not reuse `JWKSTokenVerifier`. It:

- verifies the signature against the session JWKS and caches the keys
  (`cache_keys=True`, `lifespan=3600`, per `src/cube/mcp/CLAUDE.md`);
- checks `iss` against one configured value and enforces expiry;
- does not verify `aud`;
- requires `client_id` to be in an allowlist of registered Builder Brain
  applications. Registering an app with the data team means adding its client id
  here. The allowlist also makes a single app revocable and gives the log its
  per-app field;
- requires a non-empty `email` claim whose domain is in `NETWORK_EMAIL_DOMAINS`
  (`apps.teamschools.org`, `kippmiami.org`).

The first build step decodes a real session token from the KTAF tenant and
confirms the issuer, the JWKS URL and the `client_id` claim before any code
depends on them. If they differ from the documentation, the builder stops and
reports, because the allowlist design rests on `client_id`.

`NETWORK_EMAIL_DOMAINS` lives in `src/cube/access.js`. The exchange keeps its
own copy as a Python constant and a unit test parses `access.js` and fails if
the two differ, the way `teamster.cube_sandbox.model.scope_values` already reads
`access.js`. This keeps the production auth module out of this change. (My
call.)

## Personas (decided)

- The default persona is `sheryl.swoopes@ktaf-sandbox.invalid`: network-wide
  students and full staff remit. `/token` uses it, so a new app shows data on
  day one with no choice to make.
- Each builder picks a persona per app, through the URL path (see _The
  contract_). Nothing is stored per builder, so the exchange holds no state and
  the data team has no assignment step.
- The valid personas are the ones in `src/cube/sandbox/personas.yml`, plus
  `unresolvable`. That one resolves to `unresolvable@ktaf-sandbox.invalid`,
  which has no row on purpose, so a builder can see the "unknown user" denial
  their app must handle. It is deliberately absent from `personas.yml`, and
  `GET /personas` lists it with that explanation.
- An unknown persona in the path is a 404, never a fallback to the default, so a
  typo is visible on the first request.
- `personas.yml` gets a `builder_summary` field per persona: one plain sentence
  for `GET /personas` ("Sees every school's students and all staff records").
  The existing `purpose` field stays, written for the data team.
- The image needs `personas.yml`, so the Docker build context is `src/cube/` and
  the deploy workflow's `paths:` include `src/cube/sandbox/personas.yml`. A new
  persona reaches builders on the next deploy. (My call.)

## Hosting (decided)

- Cloud Run service `cube-sandbox-exchange` in `teamster-cube-sandbox`,
  `us-central1`, the project that already holds the sandbox's data. Everything
  practice lives in that project and nothing in it touches production:
  `teamster-mcp` keeps only production services, including the production
  exchange when it is built. Putting both signing secrets in one project would
  let anyone with secret access there read both.
- This needs billing enabled on `teamster-cube-sandbox`, which has none today.
  With `--min-instances=0` the exchange costs close to nothing when idle.
- Its own runtime service account, with access to exactly 1 thing: the
  `cube-sandbox-api-secret` secret in `teamster-cube-sandbox`.
- The deploy workflow's identity (the GitHub Workload Identity Federation
  principal for this repo) gets `run.admin`, `artifactregistry.writer` and
  `iam.serviceAccountUser` on `teamster-cube-sandbox`. That grant is to the
  repo's deploy identity, not to any identity that reads production data, so the
  sandbox's no-cross-project-data rule still holds.
- `--min-instances=0`; the service is stateless.
- Deployed by a GitHub Actions workflow on push to `main` when its directory
  changes, modelled on `.github/workflows/deploy-cube-mcp.yaml` and its Workload
  Identity Federation setup. The workflow also takes `workflow_dispatch`, so the
  first deploy can run from the implementation branch and verification step 3
  happens before merge, not after. (My call.)
- The implementation ships in its own PR, after this design merges with PR
  #5267. (My call.)

## Cloud setup (decided: Charlie Bini)

Charlie Bini created `teamster-cube-sandbox` and does this setup. The repo has
no infrastructure-as-code, so the implementation plan delivers a `gcloud`
runbook for him rather than provisioning anything itself. In order:

1. Enable billing on `teamster-cube-sandbox`, and the Cloud Run, Artifact
   Registry and Secret Manager APIs.
2. Create the Artifact Registry repository the deploy workflow pushes to.
3. Create the exchange's runtime service account.
4. Create `cube-sandbox-api-secret` holding the sandbox deployment's
   `CUBEJS_API_SECRET`, copied from the sandbox deployment's settings in Cube
   Cloud. This is the one step where a person guarantees the production secret
   never reaches the exchange, so the runbook says it in bold. Grant the runtime
   account `secretAccessor` on that secret only.
5. Grant the repo's GitHub deploy identity the 3 deploy roles listed under
   _Hosting_.

The first deploy cannot run until all 5 are done.

## Logging (decided)

One structured line per issued token:
`{"event": "cube_sandbox_token", "builder": <email>, "persona": <email>, "client_id": <the app's AuthKit client id>}`.
Never the AuthKit token, never the minted token. Builder emails in Cloud Logging
are acceptable: it is internal, and the production audit design will need the
same fields. Rejections log the status and reason only.

## Constraints

- The skill's contract is fixed from our side. A change to it is a request to
  MasterBorn, not a choice here.
- The sandbox deployment's `CUBEJS_API_SECRET` is the only signing secret this
  service may ever hold.
- Python, PEP 723 inline dependencies, built into a container the way
  `src/cube/mcp/Dockerfile` does it.
- Unit tests run offline: a test generates its own RSA key pair and serves its
  own JWKS.

## Left to the builder

- The web framework (Starlette is already a transitive dependency of the MCP
  server) and the module layout under `src/cube/sandbox_exchange/`.
- Whether to share the verifier with `server.py` through a small common module
  or to copy its ~30 lines; either is fine if both are tested.
- A production mode switch (own identity, no persona paths, production secret)
  may be stubbed behind configuration, but must refuse to start without an
  explicit setting, and is not deployed.
- Rate limiting per builder, if Cloud Run's instance cap is not enough.

## Verification

1. Unit tests: `/token` maps to the default persona; `/as/<persona>/token` maps
   to that persona, `unresolvable` included; an unknown persona gets 404; a
   persona header or body field is ignored; a non-KTAF domain gets 403; a
   missing, malformed, wrong-issuer or expired token gets 401; `GET /personas`
   lists every persona in `personas.yml` plus `unresolvable`; the minted token
   decodes with `iat`, `exp` 300 seconds later, and top-level `email`.
2. A contract test that posts exactly what the skill's §5 snippet sends and
   reads exactly what it reads.
3. After deploy: sign in to a test app (or use an AuthKit token for a KTAF test
   account), exchange it, and `POST /load` against the sandbox. Expect Swoopes's
   rows. Repeat through `/as/ororo.munroe/token` and expect one school's rows,
   then through `/as/aja.ogwumike/token` and expect Cube's denial.

## Open

- **Registering apps in AuthKit.** Each Builder Brain app needs its own AuthKit
  application and redirect URIs. That procedure is operational, not code, and
  needs a named owner and turnaround on the data team.
