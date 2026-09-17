"""Throwaway (ran 2026-09-10, then deleted from tests/): re-download the suite
workbook after the owner said they had republished, and print the state needed
to decide whether a rebase is due. The fresh copy was byte-identical to the
morning's; the publish had landed on a scratch copy."""

import os
import zipfile
from pathlib import Path

import tableauserverclient as tsc

OUT = Path("/workspaces/teamster/.claude/scratch/tableau/landing")
LUID = "b3c14d67-3130-46ac-82a0-0637a5cc2da5"


def test_refresh() -> None:
    auth = tsc.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
        site_id=os.environ["TABLEAU_SITE_ID"],
    )
    server = tsc.Server(os.environ["TABLEAU_SERVER_ADDRESS"], use_server_version=True)
    with server.auth.sign_in(auth):
        wb = server.workbooks.get_by_id(LUID)
        print(f"UPDATED: {wb.updated_at}  DEFAULT_VIEW: {wb.default_view_id}")
        server.workbooks.populate_views(wb)
        for v in wb.views:
            print(f"VIEW: {v.name} {v.id}")
        got = Path(
            server.workbooks.download(
                LUID, filepath=str(OUT / "aghs-v2"), include_extract=False
            )
        )
    with zipfile.ZipFile(got) as z:
        name = next(n for n in z.namelist() if n.endswith(".twb"))
        (OUT / "aghs-v2.twb").write_bytes(z.read(name))
    print(f"DOWNLOADED {got.name} {got.stat().st_size} bytes")
