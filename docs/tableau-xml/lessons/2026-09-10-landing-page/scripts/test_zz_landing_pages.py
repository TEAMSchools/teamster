"""Throwaway (ran 2026-09-10, then deleted from tests/): download four workbooks'
XML and render landing/suite views. Run as tests/test_zz_*.py under
`uv run pytest -s` so the 1Password fixture supplies credentials.

Lesson recorded: every PNG this produced was unreadable in the harness (output
hook redaction), so the renders were useless and the XML was not."""

import os
import zipfile
from pathlib import Path

import tableauserverclient as tsc

OUT = Path("/workspaces/teamster/.claude/scratch/tableau/landing")
OUT.mkdir(parents=True, exist_ok=True)

WORKBOOKS = {
    "okrts": "08d133d6-6e48-4218-ae6d-015f7a0abe13",
    "ddi": "6d82b643-59a8-4106-b2f9-97ddf7f638e7",
    "carat": "286156c4-2f9e-4983-926b-63c9b11f44f4",
    "aghs": "b3c14d67-3130-46ac-82a0-0637a5cc2da5",
}

RENDER = {
    "okrts-landing": "105ed498-14bb-4e03-bbd7-2ded218aadae",
    "ddi-landing": "987f76fa-ddb1-4841-ae4f-2de4ea92705f",
    "carat-landing": "ae1b23ad-472d-4d3f-ad23-05d3b82898bc",
    "aghs-home": "e3f30b9d-e3aa-4342-9f00-21d0080eff53",
    "aghs-schools": "f2c62327-fff9-4805-aa1d-8f41538f74bf",
    "aghs-gpa": "6b9d6b16-d63c-4976-ac22-358f3c0759c5",
    "aghs-gb-rollup": "6e3b1df9-7cee-40b8-bb8f-0845d050530e",
    "aghs-gb-teacher": "a5d2f695-caf0-4df1-97fa-9de425a05986",
}


def _server() -> tuple[tsc.Server, tsc.PersonalAccessTokenAuth]:
    auth = tsc.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
        site_id=os.environ["TABLEAU_SITE_ID"],
    )
    return tsc.Server(
        os.environ["TABLEAU_SERVER_ADDRESS"], use_server_version=True
    ), auth


def test_download_and_render() -> None:
    server, auth = _server()
    with server.auth.sign_in(auth):
        for slug, luid in WORKBOOKS.items():
            got = Path(
                server.workbooks.download(
                    luid, filepath=str(OUT / slug), include_extract=False
                )
            )
            if got.suffix == ".twbx":
                with zipfile.ZipFile(got) as z:
                    name = next(n for n in z.namelist() if n.endswith(".twb"))
                    (OUT / f"{slug}.twb").write_bytes(z.read(name))
            print(f"DOWNLOADED {slug}: {got.name} {got.stat().st_size} bytes")

        for slug, luid in RENDER.items():
            view = server.views.get_by_id(luid)
            opts = tsc.ImageRequestOptions(
                imageresolution=tsc.ImageRequestOptions.Resolution.High
            )
            server.views.populate_image(view, opts)
            out = OUT / f"{slug}.png"
            out.write_bytes(view.image)
            print(f"RENDERED {slug}: {out.stat().st_size} bytes")
