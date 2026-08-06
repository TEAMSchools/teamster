# Reply to MasterBorn — draft

Internal draft of an outbound technical note. Not published to the docs site.
Adjust the timeline language to whatever the team commits to, then send.

---

One framing note first: this is not API access to our data. It is a sandbox that
mirrors the shape of our data so you can build against it, and when the product
is ready we repoint it at production and your integration keeps working
unchanged.

## Your questions

### Is the authorization logic a callable service?

> "Is the authorization logic that currently exists for Cube a callable service?
> Or what would need to be passed to enforce that security derivation?"

Yes, it is already a callable service — a token-exchange service on Cloud Run.
You send a verified OIDC identity token; it returns a short-lived token for the
semantic layer. You never hold our signing secret.

What you pass is **an end-user identity**. Not a scope, not a school list, not
an API key. We resolve permissions server-side from HR data at query time: which
schools or region someone covers, whether they can see sensitive staff fields,
who reports to them.

Consequence worth designing around: role changes and departures take effect with
no deploy and no action on your side.

### Safe access for developers testing externally

> "How are we going to ensure safe access for developers testing in
> non-production environments externally?"

A separate sandbox deployment reading a **synthetic dataset** — fabricated rows,
zero real student or staff records. Same schema, same semantic model, same auth
path as production. Its service account has no access to our production
warehouse at all, so the isolation does not depend on our permission rules being
correct.

Three consequences for your team:

- The integration code you write against the sandbox is the code that ships.
  Cutover is a configuration change.
- We give you test personas at different permission scopes — school-level,
  region-level, network-level — so you can see the product behave for each.
  Those are rows in the sandbox, so we can add or change them same-day.
- We are deliberately making the sandbox **stricter and messier** than
  production: narrower permissions, nulls, mid-year transfers. Anything that
  works there works on real data. The reverse is not true, which is why we are
  biasing this direction.

### Adding or exposing views and metrics

> "What's the process for adding or exposing additional views/metrics?"

You open a request naming four things: the grain, the dimensions and measures,
any filters, and the screen consuming it. Our analytics engineers implement it
in the warehouse and the semantic layer, then regenerate the catalog.

Authorship stays on our side because data classification and grain decisions
live in the underlying warehouse models. We will send you a request template.
The catalog is version-controlled, so every change shows up as a diff.

### De-identified default and early audit logs

> "I would recommend that de-identified data is the default external posture to
> start and that audit logs are accounted for early on."

Agreed on both. We went further on the first:

- **De-identified is not the default — no real data is.** Phase 1 has zero real
  records outside our infrastructure. If we later need realistic volume, a
  de-identified environment is the fallback, and it needs a re-identification
  threshold we have not set.
- **Audit:** our platform's built-in log covers administrative events, not data
  access. So we are building the data-access trail ourselves — one record per
  query with identity, view, and timestamp, never row values — into our own
  warehouse with retention we control. It lands alongside the sandbox, not
  after.

## Three things that are now yours, because your end users are staff

You confirmed the product's end users are always KTAF staff. That removes a
whole permission model from our side and makes the repoint straightforward. It
also puts three things on yours, and none of them are enforceable by our access
rules — so we need them as explicit terms rather than assumptions.

1. **Queries when the user is not signed in.** A scheduled digest, a nightly
   export, or a pre-warmed cache has no live user identity to pass. Anything in
   that category needs a different and more restricted mechanism. Tell us which
   features need it before either of us builds.
1. **Result caching across users.** Our permissions are applied per person at
   query time. A result cached for a network-level user and served to a
   school-level user bypasses that in a way we cannot see or detect.
1. **Token handling.** Identity pass-through means your product holds KTAF staff
   session tokens. Token lifetime, storage at rest, and revocation on logout are
   in scope for security review.

## Phased plan — for your approval

1. **Catalog and samples.** Days. Ready now — see below. Enough to start writing
   code and scoping screens.
1. **Sandbox with synthetic data and your access.** One to two weeks. Real
   endpoint, real auth, test personas, no real records. Includes read access to
   our model explorer, scoped to the sandbox only, so you can browse the model
   interactively.
1. **Audit trail.** Built alongside the sandbox, not after.
1. **Repoint at production data.** Weeks. Unblocked, now that we know your end
   users are staff.

Steps 1 through 3 need nothing further from you. Tell us if the sequence or the
timing does not fit your plan.

## The catalog — available now

Everything the semantic layer exposes: 6 views, 40 measures, 295 dimensions,
with types and descriptions. No data in it.

- **Readable reference:**
  `https://teamschools.github.io/teamster/reference/cube-semantic-catalog/`
- **Machine-readable, parse this one:**
  `https://teamschools.github.io/teamster/reference/cube-catalog-meta.json`

The readable page also carries a ten-item gotchas list. Two of those will cost
you a day each if you find them the hard way:

- **Numeric measures come back as JSON strings** — `"900"`, not `900`. Every
  measure, including counts. Coerce at the parse boundary.
- **A query requesting one field the caller cannot see fails entirely** — the
  whole query errors rather than dropping that column. A screen built against a
  broadly-scoped user will error outright for a narrowly-scoped one, so design
  for it.

## A REST request you can run

`POST /cubejs-api/v1/load`. The `Authorization` header takes the **raw token,
with no `Bearer` prefix** — that trips up nearly everyone once.

```bash
curl -s -X POST "$cube_url/cubejs-api/v1/load" \
  -H "Authorization: $cube_token" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {
      "measures": ["staff_directory.count_employees"],
      "dimensions": ["staff_directory.regions_region_name"],
      "filters": [
        {"member": "staff_directory.is_primary_position", "operator": "equals", "values": ["true"]},
        {"member": "staff_directory.status_name", "operator": "equals", "values": ["Active"]}
      ],
      "timeDimensions": [
        {"dimension": "staff_directory.dates_date_day", "dateRange": ["2026-08-05", "2026-08-05"]}
      ],
      "order": {"staff_directory.count_employees": "desc"}
    }
  }'
```

Response shape, with illustrative values:

```json
{
  "query": {
    "...": "your query, normalized — do not diff it against what you sent"
  },
  "annotation": {
    "measures": {
      "staff_directory.count_employees": {
        "shortTitle": "Count Employees",
        "description": "Distinct employees in scope...",
        "type": "number"
      }
    },
    "dimensions": {
      "staff_directory.regions_region_name": {
        "shortTitle": "Regions Region Name",
        "type": "string"
      }
    }
  },
  "data": [
    {
      "staff_directory.regions_region_name": "Region A",
      "staff_directory.count_employees": "900"
    },
    {
      "staff_directory.regions_region_name": null,
      "staff_directory.count_employees": "5"
    }
  ]
}
```

Every member name is dotted `view.member` — bare names do not resolve. Use
`annotation` to label output instead of hard-coding titles; it stays correct
when a description changes.

You cannot run this against the sandbox until step 2 lands, so for now build
against the catalog and mock the envelope above. We will send the endpoint and
the token-exchange details with the sandbox.
