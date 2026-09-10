"""Throwaway (ran 2026-09-10, then deleted from tests/): download four in-house
dashboards' .twb (no extract) and grep for navigation XML, because none of the
four workbooks already in hand carried a Go to Sheet action or a navigation
button.

A first version paged every workbook on the site; the auto-mode classifier
denied it. This four-luid version ran. Findings are in ../lessons.md under
"Navigation XML exists on this server"."""

import os
import re
import zipfile
from pathlib import Path

import tableauserverclient as tsc

OUT = Path("/workspaces/teamster/.claude/scratch/tableau/harvest")
OUT.mkdir(parents=True, exist_ok=True)
LUIDS = {
    "fresh": "0decd81d-f1c0-464a-bf2f-3546af11d47c",
    "hs-early-warning": "6333e047-e7a9-4d8f-a740-3df30f179d11",
    "apm": "eb91563d-760b-4f2d-b9f8-65437fe22242",
    "gradebook-gpa": "5046a976-ed0e-4c77-93fe-78b732cb5548",
}


def test_harvest() -> None:
    auth = tsc.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
        site_id=os.environ["TABLEAU_SITE_ID"],
    )
    server = tsc.Server(os.environ["TABLEAU_SERVER_ADDRESS"], use_server_version=True)
    with server.auth.sign_in(auth):
        for slug, luid in LUIDS.items():
            got = Path(
                server.workbooks.download(
                    luid, filepath=str(OUT / slug), include_extract=False
                )
            )
            if got.suffix == ".twbx":
                with zipfile.ZipFile(got) as z:
                    name = next(n for n in z.namelist() if n.endswith(".twb"))
                    data = z.read(name)
                got.unlink()
                got = OUT / f"{slug}.twb"
                got.write_bytes(data)
            text = got.read_text(encoding="utf-8", errors="replace")
            nav = len(re.findall("navigat", text, re.I))
            cmds = sorted(set(re.findall(r"command='(tsc:[a-z-]+)'", text)))
            print(
                f"HARVEST {slug}: navigat={nav} buttons={text.count('<button ')} cmds={cmds}"
            )
