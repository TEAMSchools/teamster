"""PII-SAFE live Finalsite API tooling: creds diagnostic + export-coverage
validation. Reuses the production FinalsiteResource + EnvVar creds (1Password via
conftest). Prints only aggregates / field names / API paths — never a student
value, the token, or the secret.
"""

import os
import re
from collections import Counter

from dagster import EnvVar, build_resources

from teamster.libraries.finalsite.api.resources import FinalsiteResource

DISTRICTS = ["kippnewark", "kippmiami"]


def _describe(name: str) -> str:
    v = os.environ.get(name)
    if v is None:
        return f"{name}: UNSET"
    return f"{name}: set len={len(v)} op_ref={v.startswith('op://')} blank={v.strip() == ''}"


def test_finalsite_creds_diagnostic():
    """Report which districts have resolvable API creds. No secret values."""
    for d in DISTRICTS:
        s = d.upper()
        print(f"\n[{d}]")
        print("  " + _describe(f"FINALSITE_CREDENTIAL_ID_{s}"))
        print("  " + _describe(f"FINALSITE_SECRET_{s}"))


def _variants(v) -> set[str]:
    """Normalized comparison variants of a scalar value."""
    s = ("" if v is None else str(v)).strip()
    out: set[str] = set()
    if not s:
        return out
    low = " ".join(s.lower().split())
    out.add(low)
    digits = re.sub(r"\D", "", s)
    if len(digits) >= 7:  # phone-ish
        out.add(digits)
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if m:  # date-ish
        out.add(m.group(1))
    return out


def _candidates(contact: dict) -> list[tuple[str, object]]:
    """Labeled (api_field_path, value) pairs from a contact, with custom-field
    names preserved and relationship/household structure flattened."""
    out: list[tuple[str, object]] = []
    for k, v in contact.items():
        if k in ("custom_attributes", "track_attributes", "id_attributes"):
            tag = k.split("_")[0]
            for a in v or []:
                out.append((f"{tag}:{a.get('field_name')}", a.get("value")))
        elif k == "households":
            for h in v or []:
                for hk, hv in (h or {}).items():
                    out.append((f"household.{hk}", hv))
        elif k == "relationships":
            for rel in v or []:
                rt = rel.get("rel_type")
                name = rel.get("rel_name")
                out.append((f"rel:{rt}:name", name))
                for tok in str(name or "").split():  # so first/last match
                    out.append((f"rel:{rt}:name_token", tok))
                rc = rel.get("contact")
                if isinstance(rc, dict):
                    for rk, rv in rc.items():
                        if isinstance(rv, (str, int, float)):
                            out.append((f"rel:{rt}:{rk}", rv))
                        elif isinstance(rv, dict) and rk.startswith("phone"):
                            out.append((f"rel:{rt}:{rk}", rv.get("number")))
        elif k in ("grade", "school_year") and isinstance(v, dict):
            for kk in ("name", "canonical_name", "start_year"):
                if v.get(kk) is not None:
                    out.append((f"{k}.{kk}", v.get(kk)))
        elif k in ("phone_1", "phone_2", "phone_3") and isinstance(v, dict):
            out.append((k, v.get("number")))
        elif isinstance(v, (str, int, float, bool)):
            out.append((k, v))
    return out


def test_validate_export_coverage():
    """For each column in the new SFTP export, check (by value) whether the live
    API reproduces it for the same student, and report which API field carries
    it. Aggregates only."""
    import csv
    import pathlib

    district = os.environ.get("FINALSITE_VALIDATE_DISTRICT", "kippmiami")
    suffix = district.upper()
    cid = os.environ.get(f"FINALSITE_CREDENTIAL_ID_{suffix}")
    sec = os.environ.get(f"FINALSITE_SECRET_{suffix}")
    csv_path = (
        pathlib.Path(__file__).resolve().parents[2]
        / ".claude/scratch/finalsite_export_new.csv"
    )
    if not (cid and sec):
        import pytest

        pytest.skip(f"no {district} creds")
    if not csv_path.exists():
        import pytest

        pytest.skip(f"no export csv at {csv_path}")

    sample_n = int(os.environ.get("VALIDATE_SAMPLE", "60"))
    with csv_path.open(newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if (r.get("Finalsite ID") or "").strip()]
    columns = [c for c in rows[0].keys() if c and c != "Finalsite ID"]
    sample = rows[:sample_n]

    match = {c: 0 for c in columns}
    nonblank = {c: 0 for c in columns}
    boolish = {c: 0 for c in columns}
    paths = {c: Counter() for c in columns}
    fetched = notfound = 0

    with build_resources(
        {
            "finalsite": FinalsiteResource(
                server=district,
                credential_id=EnvVar(f"FINALSITE_CREDENTIAL_ID_{suffix}"),
                secret=EnvVar(f"FINALSITE_SECRET_{suffix}"),
            )
        }
    ) as resources:
        fs = resources.finalsite
        for r in sample:
            fid = r["Finalsite ID"].strip()
            try:
                contact = (
                    fs.get(
                        path="contacts", id=fid, params={"includes": "relationships"}
                    )
                    .json()
                    .get("contact", {})
                )
            except Exception:  # noqa: BLE001
                notfound += 1
                continue
            fetched += 1
            cands = [(lbl, _variants(val)) for lbl, val in _candidates(contact)]
            for c in columns:
                ev = r.get(c)
                evs = _variants(ev)
                if not evs:
                    continue
                nonblank[c] += 1
                if (ev or "").strip().lower() in {
                    "true",
                    "false",
                    "yes",
                    "no",
                    "y",
                    "n",
                }:
                    boolish[c] += 1
                hit = [lbl for lbl, cv in cands if cv & evs]
                if hit:
                    match[c] += 1
                    paths[c][hit[0]] += 1

    print(
        f"\n# Export→API coverage ({district}); fetched {fetched}/{len(sample)}, "
        f"not-found {notfound}\n"
    )
    for c in columns:
        nb = nonblank[c]
        if nb == 0:
            print(f"  {c}: — (blank across sample)")
            continue
        pct = round(100 * match[c] / nb)
        top = paths[c].most_common(1)
        via = f"  via `{top[0][0]}`" if top else "  (NO API SOURCE FOUND)"
        flag = "  [bool: low-confidence]" if boolish[c] > nb / 2 else ""
        print(f"  {c}: {pct}% ({match[c]}/{nb}){via}{flag}")


def test_contacts_list_vs_get():
    """Does GET /contacts (paginated list) return the same field payload as
    GET /contacts/{id}? Compares key sets + nested-collection lengths. No PII."""
    district = os.environ.get("FINALSITE_VALIDATE_DISTRICT", "kippmiami")
    suffix = district.upper()
    if not os.environ.get(f"FINALSITE_CREDENTIAL_ID_{suffix}"):
        import pytest

        pytest.skip(f"no {district} creds")

    nested = [
        "custom_attributes",
        "track_attributes",
        "id_attributes",
        "relationships",
        "households",
    ]

    with build_resources(
        {
            "finalsite": FinalsiteResource(
                server=district,
                credential_id=EnvVar(f"FINALSITE_CREDENTIAL_ID_{suffix}"),
                secret=EnvVar(f"FINALSITE_SECRET_{suffix}"),
            )
        }
    ) as resources:
        fs = resources.finalsite
        years = fs.get(path="school_years").json().get("school_years", [])
        listed: list = []
        chosen = None
        for y in sorted(years, key=lambda y: y.get("start_year") or 0, reverse=True):
            resp = fs.get(
                path="contacts",
                params={
                    "school_year_id": y.get("id"),
                    "count": 25,
                    "includes": "relationships",
                },
            ).json()
            if resp.get("contacts"):
                listed, chosen = resp["contacts"], y
                break
        print(
            f"\n# list-vs-get ({district}); school_year start="
            f"{chosen.get('start_year') if chosen else None}; list page n={len(listed)}"
        )
        if not listed:
            return

        list_keys = sorted({k for c in listed for k in c})
        print(f"  keys present on list items ({len(list_keys)}): {list_keys}")
        print("  nested-collection presence on LIST items (non-empty count):")
        for k in nested:
            ne = sum(1 for c in listed if (c.get(k) or []))
            print(f"    {k}: {ne}/{len(listed)}")

        same = 0
        get_only: Counter = Counter()
        list_only: Counter = Counter()
        nested_len_match = {k: 0 for k in nested}
        n = 0
        for lc in listed:
            gc = (
                fs.get(
                    path="contacts", id=lc["id"], params={"includes": "relationships"}
                )
                .json()
                .get("contact", {})
            )
            n += 1
            lk, gk = set(lc), set(gc)
            if lk == gk:
                same += 1
            for k in gk - lk:
                get_only[k] += 1
            for k in lk - gk:
                list_only[k] += 1
            for k in nested:
                if len(lc.get(k) or []) == len(gc.get(k) or []):
                    nested_len_match[k] += 1
        print(f"\n  identical key set list==get: {same}/{n}")
        print(f"  keys in GET-by-id but MISSING from list: {dict(get_only)}")
        print(f"  keys in list but missing from GET: {dict(list_only)}")
        print("  nested length list==get:")
        for k in nested:
            print(f"    {k}: {nested_len_match[k]}/{n}")


def test_expand_relationships_contact():
    """Confirm ?includes=contacts.relationships.contact inlines the full related
    (guardian) contact — so guardian email/phone come from the paginated list in
    one call. Aggregates only."""
    district = os.environ.get("FINALSITE_VALIDATE_DISTRICT", "kippmiami")
    suffix = district.upper()
    if not os.environ.get(f"FINALSITE_CREDENTIAL_ID_{suffix}"):
        import pytest

        pytest.skip(f"no {district} creds")

    with build_resources(
        {
            "finalsite": FinalsiteResource(
                server=district,
                credential_id=EnvVar(f"FINALSITE_CREDENTIAL_ID_{suffix}"),
                secret=EnvVar(f"FINALSITE_SECRET_{suffix}"),
            )
        }
    ) as resources:
        fs = resources.finalsite
        years = fs.get(path="school_years").json().get("school_years", [])
        cur = next((y for y in years if (y.get("start_year") or 0) == 2026), None)
        sy_id = (cur or max(years, key=lambda y: y.get("start_year") or 0)).get("id")

        for token in ["relationships", "contacts.relationships.contact"]:
            resp = fs.get(
                path="contacts",
                params={"school_year_id": sy_id, "count": 25, "includes": token},
            ).json()
            contacts = resp.get("contacts", [])
            rels = full = with_email = with_phone = 0
            keyset: Counter = Counter()
            for c in contacts:
                for rel in c.get("relationships") or []:
                    rels += 1
                    rc = rel.get("contact")
                    if isinstance(rc, dict):
                        keyset.update(rc.keys())
                        if any(k in rc for k in ("email", "first_name", "phone_1")):
                            full += 1
                        if rc.get("email"):
                            with_email += 1
                        if (rc.get("phone_1") or {}).get("number"):
                            with_phone += 1
            print(f"\n## includes={token!r} (n_contacts={len(contacts)}, rels={rels})")
            print(f"    related-contact is FULL object: {full}/{rels}")
            print(
                f"    related-contact has email: {with_email}/{rels}; "
                f"phone_1.number: {with_phone}/{rels}"
            )
            print(f"    distinct keys seen on related contact: {sorted(keyset)}")


def test_fields_catalog_coverage():
    """List the /fields catalog and check how many enumerated fields we actually
    observe populated across a contacts sample (students + expanded relatives).
    Aggregates only; full field list written to scratch."""
    import pathlib

    district = os.environ.get("FINALSITE_VALIDATE_DISTRICT", "kippmiami")
    suffix = district.upper()
    if not os.environ.get(f"FINALSITE_CREDENTIAL_ID_{suffix}"):
        import pytest

        pytest.skip(f"no {district} creds")

    sample_n = int(os.environ.get("FIELDS_SAMPLE", "150"))

    with build_resources(
        {
            "finalsite": FinalsiteResource(
                server=district,
                credential_id=EnvVar(f"FINALSITE_CREDENTIAL_ID_{suffix}"),
                secret=EnvVar(f"FINALSITE_SECRET_{suffix}"),
            )
        }
    ) as resources:
        fs = resources.finalsite
        fields = fs.get(path="fields").json().get("fields", [])
        by_group: Counter = Counter()
        by_ctype: Counter = Counter()
        for f in fields:
            by_group[f.get("grouping")] += 1
            by_ctype[f.get("ctype")] += 1

        # observe populated field names across a sample (students + relatives)
        years = fs.get(path="school_years").json().get("school_years", [])
        cur = next((y for y in years if (y.get("start_year") or 0) == 2026), None)
        sy_id = (cur or max(years, key=lambda y: y.get("start_year") or 0)).get("id")
        observed: set[str] = set()
        seen = 0
        cursor = None
        while seen < sample_n:
            p = {
                "school_year_id": sy_id,
                "count": 25,
                "includes": "contacts.relationships.contact",
            }
            if cursor:
                p["cursor"] = cursor
            resp = fs.get(path="contacts", params=p).json()
            batch = resp.get("contacts", [])

            def harvest(c):
                if not isinstance(c, dict):
                    return
                for k, v in c.items():
                    if isinstance(v, (str, int, float, bool)) and v not in ("", None):
                        observed.add(k)
                for nk in ("custom_attributes", "track_attributes", "id_attributes"):
                    for a in c.get(nk) or []:
                        if a.get("value") not in ("", None):
                            observed.add(a.get("field_name"))
                for rel in c.get("relationships") or []:
                    harvest(rel.get("contact"))

            for c in batch:
                harvest(c)
                seen += 1
            cursor = resp.get("meta", {}).get("next_cursor")
            if not cursor:
                break

        field_names = {f.get("name") for f in fields}
        matched = field_names & observed
        unobserved = sorted(field_names - observed)
        # per-grouping coverage
        grp_total: Counter = Counter()
        grp_obs: Counter = Counter()
        for f in fields:
            g = f.get("grouping")
            grp_total[g] += 1
            if f.get("name") in observed:
                grp_obs[g] += 1

        out = pathlib.Path(__file__).resolve().parents[2] / ".claude/scratch"
        (out / "fs_fields_all.txt").write_text(
            "\n".join(
                f"{f.get('grouping')}\t{f.get('ctype')}\t{f.get('name')}"
                for f in sorted(
                    fields, key=lambda f: (f.get("grouping") or "", f.get("name") or "")
                )
            )
        )
        (out / "fs_fields_unobserved.txt").write_text("\n".join(unobserved))

        print(f"\n# /fields catalog ({district}): {len(fields)} fields")
        print("  by grouping:")
        for g, n in by_group.most_common():
            print(f"    {g}: {n}")
        print("  by ctype:")
        for c, n in by_ctype.most_common():
            print(f"    {c}: {n}")
        print(
            f"\n# observed populated over {seen} contacts (+relatives): "
            f"{len(matched)}/{len(fields)} ({round(100 * len(matched) / len(fields))}%)"
        )
        print("  per-grouping observed/total:")
        for g in sorted(grp_total, key=lambda g: -grp_total[g]):
            print(f"    {g}: {grp_obs[g]}/{grp_total[g]}")
        print(
            f"\n  unobserved fields: {len(unobserved)} "
            f"(full list -> .claude/scratch/fs_fields_unobserved.txt)"
        )


def test_hunt_enrolled_date():
    """Hunt for the export's Enrolled Date in the API: (1) inspect contact_statuses
    shape, (2) probe candidate expansion tokens, (3) deep-search each student's
    full payload for the enrolled timestamp at minute precision. Aggregates only."""
    import csv
    import pathlib
    import re as _re

    district = os.environ.get("FINALSITE_VALIDATE_DISTRICT", "kippmiami")
    suffix = district.upper()
    csv_path = (
        pathlib.Path(__file__).resolve().parents[2]
        / ".claude/scratch/finalsite_export_new.csv"
    )
    if not os.environ.get(f"FINALSITE_CREDENTIAL_ID_{suffix}") or not csv_path.exists():
        import pytest

        pytest.skip("no creds or export csv")

    def dnums(s):
        """Return (date_part, minute_key) for any date/datetime-looking string."""
        s = str(s or "")
        d = _re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
        if not d:
            return (None, None)
        date_part = "".join(d.groups())
        digits = _re.sub(r"\D", "", s)
        minute_key = digits[:12] if len(digits) >= 12 else None  # YYYYMMDDHHMM
        return (date_part, minute_key)

    def leaves(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield from leaves(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for v in obj:
                yield from leaves(v, f"{path}[]")
        elif isinstance(obj, str):
            yield (path, obj)

    with build_resources(
        {
            "finalsite": FinalsiteResource(
                server=district,
                credential_id=EnvVar(f"FINALSITE_CREDENTIAL_ID_{suffix}"),
                secret=EnvVar(f"FINALSITE_SECRET_{suffix}"),
            )
        }
    ) as resources:
        fs = resources.finalsite

        # (1) contact_statuses shape
        cs = fs.get(path="contact_statuses").json().get("contact_statuses", [])
        print(
            f"\n## contact_statuses: {len(cs)} items; keys per item: "
            f"{sorted(cs[0].keys()) if cs else []}"
        )

        # (2) probe candidate expansion tokens (does any add new keys / not error?)
        years = fs.get(path="school_years").json().get("school_years", [])
        cur = next((y for y in years if (y.get("start_year") or 0) == 2026), None)
        sy_id = (cur or max(years, key=lambda y: y.get("start_year") or 0)).get("id")
        base = fs.get(
            path="contacts", params={"school_year_id": sy_id, "count": 2}
        ).json()
        base_keys = {k for c in base.get("contacts", []) for k in c}
        print("\n## expansion-token probe (status/HTTP + new keys vs baseline):")
        for tok in [
            "contacts.statuses",
            "contacts.status_history",
            "contacts.workflow",
            "contacts.enrollments",
            "contacts.school_enrollments",
            "contacts.contact_status",
            "contacts.status",
        ]:
            try:
                r = fs.get(
                    path="contacts",
                    params={"school_year_id": sy_id, "count": 2, "includes": tok},
                )
                cc = r.json().get("contacts", [])
                newk = ({k for c in cc for k in c} - base_keys) if cc else set()
                print(
                    f"    {tok}: HTTP {r.status_code}; new keys: {sorted(newk) or 'none'}"
                )
            except Exception as e:  # noqa: BLE001
                code = getattr(getattr(e, "response", None), "status_code", "?")
                print(f"    {tok}: HTTP {code} (rejected)")

        # (3) deep-search each student's full payload for the enrolled timestamp
        with csv_path.open(newline="") as fh:
            rows = [
                r
                for r in csv.DictReader(fh)
                if (r.get("Finalsite ID") or "").strip()
                and (r.get("Enrolled Date") or "").strip()
            ][:20]
        minute_hit: Counter = Counter()
        date_hit: Counter = Counter()
        n = 0
        for r in rows:
            try:
                c = (
                    fs.get(path="contacts", id=r["Finalsite ID"].strip())
                    .json()
                    .get("contact", {})
                )
            except Exception:  # noqa: BLE001
                continue
            n += 1
            ed_date, ed_min = dnums(r["Enrolled Date"])
            for p, v in leaves(c):
                vd, vm = dnums(v)
                if ed_min and vm and ed_min == vm:
                    minute_hit[p] += 1
                elif ed_date and vd and ed_date == vd:
                    date_hit[p] += 1
        print(f"\n## Enrolled Date deep-search over {n} students:")
        print(
            f"    MINUTE-precision matches (exact timestamp): "
            f"{dict(minute_hit) or 'NONE'}"
        )
        print(
            f"    date-only matches (likely coincidental): {dict(date_hit) or 'NONE'}"
        )


def _race_set(v) -> set[str]:
    if isinstance(v, list):
        parts = v
    else:
        parts = re.split(r"[|,/]", str(v or ""))
    return {p.strip().lower() for p in parts if str(p).strip()}


def test_validate_export_coverage_pass2():
    """Second pass: follow relationships to parent contacts; inspect Race and
    Enrolled Date raw representation; confirm boolean field names via /fields.
    Aggregates only — no student values."""
    import csv
    import pathlib

    district = os.environ.get("FINALSITE_VALIDATE_DISTRICT", "kippmiami")
    suffix = district.upper()
    cid = os.environ.get(f"FINALSITE_CREDENTIAL_ID_{suffix}")
    csv_path = (
        pathlib.Path(__file__).resolve().parents[2]
        / ".claude/scratch/finalsite_export_new.csv"
    )
    if not cid:
        import pytest

        pytest.skip(f"no {district} creds")
    if not csv_path.exists():
        import pytest

        pytest.skip("no export csv")

    sample_n = int(os.environ.get("VALIDATE_SAMPLE2", "40"))
    with csv_path.open(newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if (r.get("Finalsite ID") or "").strip()]
    sample = rows[:sample_n]

    with build_resources(
        {
            "finalsite": FinalsiteResource(
                server=district,
                credential_id=EnvVar(f"FINALSITE_CREDENTIAL_ID_{suffix}"),
                secret=EnvVar(f"FINALSITE_SECRET_{suffix}"),
            )
        }
    ) as resources:
        fs = resources.finalsite
        cache: dict = {}

        def get_contact(cid_):
            if cid_ not in cache:
                try:
                    cache[cid_] = (
                        fs.get(
                            path="contacts",
                            id=cid_,
                            params={"includes": "relationships"},
                        )
                        .json()
                        .get("contact", {})
                    )
                except Exception:  # noqa: BLE001
                    cache[cid_] = None
            return cache[cid_]

        # ---- /fields name confirmation ----
        fields = fs.get(path="fields").json().get("fields", [])
        print(
            "\n## fields matching race/ethnic/latino/hispanic/media/sped/iep/"
            "enroll/date (name | ctype):"
        )
        pat = re.compile(
            r"race|ethnic|latino|hispan|media|sped|special|iep|enroll|date", re.I
        )
        for f in fields:
            nm, dn = f.get("name") or "", f.get("display_name") or ""
            if pat.search(nm) or pat.search(dn):
                print(f"    {nm}  ({f.get('ctype')})")

        # ---- per-student: race format, enrolled-date search, parent fields ----
        race_set_match = race_nonblank = 0
        race_value_types: Counter = Counter()
        race_field_names: Counter = Counter()
        enrolled_hit = enrolled_nonblank = 0
        enrolled_via: Counter = Counter()
        # parent tallies keyed by sub-field
        ptot: Counter = Counter()
        phit: Counter = Counter()

        def cattrs(contact):
            return {
                a.get("field_name"): a.get("value")
                for a in (contact.get("custom_attributes") or [])
            }

        for r in sample:
            stu = get_contact(r["Finalsite ID"].strip())
            if not stu:
                continue
            ca = cattrs(stu)

            # Race
            exp_race = r.get("Race - Multi-Racial")
            if (exp_race or "").strip():
                race_nonblank += 1
                rfield = next((k for k in ca if "race" in k.lower()), None)
                if rfield:
                    race_field_names[rfield] += 1
                    rv = ca[rfield]
                    race_value_types[type(rv).__name__] += 1
                    if _race_set(rv) == _race_set(exp_race):
                        race_set_match += 1

            # Enrolled Date: any base/custom/track date value == export date part
            exp_enr = (r.get("Enrolled Date") or "").strip()
            if exp_enr:
                enrolled_nonblank += 1
                want = exp_enr[:10]
                found = None
                pool = (
                    list(stu.items())
                    + [
                        (f"custom:{a.get('field_name')}", a.get("value"))
                        for a in (stu.get("custom_attributes") or [])
                    ]
                    + [
                        (f"track:{a.get('field_name')}", a.get("value"))
                        for a in (stu.get("track_attributes") or [])
                    ]
                )
                for lbl, val in pool:
                    if (
                        isinstance(val, str)
                        and val[:10] == want
                        and re.match(r"\d{4}-\d{2}-\d{2}", val)
                    ):
                        found = lbl
                        break
                if found:
                    enrolled_hit += 1
                    enrolled_via[found] += 1

            # Parents: fetch related contact by export Parent N Finalsite ID
            rels = {
                rel.get("rel_id"): rel.get("rel_type")
                for rel in (stu.get("relationships") or [])
            }
            for n in (1, 2, 3, 4):
                pfid = (r.get(f"Parent {n} Finalsite ID") or "").strip()
                if not pfid:
                    continue
                pc = get_contact(pfid)
                # Parent Finalsite ID resolvable as a contact / rel_id?
                ptot["finalsite_id_resolves"] += 1
                if pc is not None:
                    phit["finalsite_id_resolves"] += 1
                ptot["is_in_relationships"] += 1
                if pfid in rels:
                    phit["is_in_relationships"] += 1
                if pc is None:
                    continue
                pcv = {
                    "first": (pc.get("first_name") or "").strip().lower(),
                    "last": (pc.get("last_name") or "").strip().lower(),
                    "email": (pc.get("email") or "").strip().lower(),
                }
                phones = {
                    re.sub(r"\D", "", (pc.get(f"phone_{i}") or {}).get("number") or "")
                    for i in (1, 2, 3)
                }
                phones.discard("")
                checks = {
                    "First Name": (
                        (r.get(f"Parent {n} First Name") or "").strip().lower(),
                        pcv["first"],
                    ),
                    "Last Name": (
                        (r.get(f"Parent {n} Last Name") or "").strip().lower(),
                        pcv["last"],
                    ),
                    "Email": (
                        (r.get(f"Parent {n} Email") or "").strip().lower(),
                        pcv["email"],
                    ),
                }
                for field, (ev, av) in checks.items():
                    if ev:
                        ptot[field] += 1
                        if ev == av:
                            phit[field] += 1
                ev_phone = re.sub(
                    r"\D", "", r.get(f"Parent {n} Primary Phone Number") or ""
                )
                if ev_phone:
                    ptot["Phone Number"] += 1
                    if ev_phone in phones:
                        phit["Phone Number"] += 1
                ev_rel = (r.get(f"Parent {n} Relationship") or "").strip().lower()
                if ev_rel:
                    ptot["Relationship(vs rel_type)"] += 1
                    if ev_rel == str(rels.get(pfid) or "").lower():
                        phit["Relationship(vs rel_type)"] += 1

    print("\n## Race - Multi-Racial")
    print(f"    field name(s): {dict(race_field_names)}")
    print(f"    API value type: {dict(race_value_types)}")
    if race_nonblank:
        print(
            f"    set-equal match (after parsing | , /): "
            f"{round(100 * race_set_match / race_nonblank)}% "
            f"({race_set_match}/{race_nonblank})"
        )

    print("\n## Enrolled Date")
    if enrolled_nonblank:
        print(
            f"    reproduced by a date field: "
            f"{round(100 * enrolled_hit / enrolled_nonblank)}% "
            f"({enrolled_hit}/{enrolled_nonblank})  via {dict(enrolled_via)}"
        )

    print("\n## Parent fields (matched against the related parent contact):")
    for k in [
        "finalsite_id_resolves",
        "is_in_relationships",
        "First Name",
        "Last Name",
        "Email",
        "Phone Number",
        "Relationship(vs rel_type)",
    ]:
        t = ptot[k]
        if t:
            print(f"    {k}: {round(100 * phit[k] / t)}% ({phit[k]}/{t})")
