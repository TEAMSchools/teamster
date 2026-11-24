"""Build Google Docs requests that add a playbook as a tab of the shared doc.

Drive's HTML import makes a whole doc and cannot make a tab, so a tab is built
with the Docs connector's ``update_doc`` in three calls: ``addDocumentTab``,
then ``skeleton`` (one empty table per section), then, after ``read_doc``,
``fill`` (shade the title and header rows, insert every cell's text). Cells
are filled from the highest index down, so no insert moves a later one.

Input is ``render_doc.py``'s HTML parsed back into tables, so a tab and a
standalone doc never drift. A row whose cells are all bold in the HTML is a
header row; the first row is the section title.
"""

from __future__ import annotations

import argparse
import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Sequence

TITLE_BG = {"red": 0.851, "green": 0.886, "blue": 0.953}
HEADER_BG = {"red": 0.937, "green": 0.937, "blue": 0.937}

Cell = tuple[str, bool]  # text, bold


class _Tables(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[Cell]]] = []
        self._row: list[Cell] | None = None
        self._cell: list[str] | None = None
        self._span, self._href, self._bold = 1, "", False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self.tables.append([])
        elif tag == "tr":
            self._row = []
        elif tag == "td":
            self._cell, self._span, self._href, self._bold = (
                [],
                int(a.get("colspan") or 1),
                "",
                False,
            )
        elif tag == "a":
            self._href = a.get("href") or ""
        elif tag == "b":
            self._bold = True

    def handle_endtag(self, tag):
        if tag == "td" and self._row is not None and self._cell is not None:
            text = "".join(self._cell).strip()
            if self._href:
                text = self._href
            self._row.append((text, self._bold))
            self._row.extend([("", False)] * (self._span - 1))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.tables[-1].append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def parse_tables(page: str) -> list[list[list[Cell]]]:
    """Each table as rows of (text, bold); a colspan cell is padded with blanks."""
    p = _Tables()
    p.feed(page)
    return p.tables


def skeleton(tables: list[list[list[Cell]]], tab_id: str) -> list[dict]:
    return [
        {
            "insertTable": {
                "rows": len(t),
                "columns": len(t[0]),
                "endOfSegmentLocation": {"tabId": tab_id},
            }
        }
        for t in tables
    ]


def _find_tab(tabs: list[dict], tab_id: str) -> dict | None:
    for tab in tabs:
        if tab.get("tabProperties", {}).get("tabId") == tab_id:
            return tab
        found = _find_tab(tab.get("childTabs", []), tab_id)
        if found:
            return found
    return None


def _is_header(row: list[Cell]) -> bool:
    filled = [c for c in row if c[0]]
    return len(filled) > 1 and all(b for _, b in filled)


def fill(doc: dict, tab_id: str, tables: list[list[list[Cell]]]) -> list[dict]:
    """Shading requests first (positions as read), then text inserts, highest first."""
    tab = _find_tab(doc.get("tabs", []), tab_id)
    if tab is None:
        raise ValueError(f"tab {tab_id} not in the document")
    found = [e for e in tab["documentTab"]["body"]["content"] if "table" in e]
    if len(found) != len(tables):
        raise ValueError(f"tab has {len(found)} tables, expected {len(tables)}")
    shade, inserts = [], []
    for element, rows in zip(found, tables, strict=True):
        start, cols = element["startIndex"], len(rows[0])
        for r, row in enumerate(rows):
            bg = TITLE_BG if r == 0 else HEADER_BG if _is_header(row) else None
            if bg:
                shade.append(
                    {
                        "updateTableCellStyle": {
                            "tableCellStyle": {
                                "backgroundColor": {"color": {"rgbColor": bg}}
                            },
                            "fields": "backgroundColor",
                            "tableRange": {
                                "tableCellLocation": {
                                    "tableStartLocation": {
                                        "index": start,
                                        "tabId": tab_id,
                                    },
                                    "rowIndex": r,
                                    "columnIndex": 0,
                                },
                                "rowSpan": 1,
                                "columnSpan": cols,
                            },
                        }
                    }
                )
            cells = element["table"]["tableRows"][r]["tableCells"]
            for c, (text, _) in enumerate(row):
                if text:
                    inserts.append((cells[c]["content"][0]["startIndex"], text))
    inserts.sort(key=lambda x: -x[0])
    return shade + [
        {"insertText": {"text": t, "location": {"index": i, "tabId": tab_id}}}
        for i, t in inserts
    ]


def apply(
    doc_id: str, title: str, tables: list[list[list[Cell]]]
) -> str:  # pragma: no cover - live API
    """Run all three steps through the Docs API as the ADC service account,
    which needs Editor on the doc. Returns the new tab's id."""
    import google.auth
    from googleapiclient.discovery import build

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/documents"])
    docs = build("docs", "v1", credentials=creds).documents()

    def run(reqs: list[dict]) -> dict:
        return docs.batchUpdate(documentId=doc_id, body={"requests": reqs}).execute()

    reply = run([{"addDocumentTab": {"tabProperties": {"title": title}}}])
    tab_id = reply["replies"][0]["addDocumentTab"]["tabProperties"]["tabId"]
    run(skeleton(tables, tab_id))
    run(
        fill(
            docs.get(documentId=doc_id, includeTabsContent=True).execute(),
            tab_id,
            tables,
        )
    )
    return tab_id


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Docs requests for one playbook tab.")
    p.add_argument("step", choices=["skeleton", "fill", "apply"])
    p.add_argument("--html", required=True, type=Path, help="render_doc.py output")
    p.add_argument("--tab-id", help="skeleton and fill: the tab to build")
    p.add_argument("--doc", type=Path, help="fill only: read_doc JSON")
    p.add_argument("--doc-id", help="apply only: the Service Playbooks doc")
    p.add_argument("--title", help="apply only: the new tab's title")
    args = p.parse_args(argv)
    tables = parse_tables(args.html.read_text())
    if args.step == "apply":
        print(apply(args.doc_id, args.title, tables))
        return 0
    try:
        if args.step == "skeleton":
            reqs = skeleton(tables, args.tab_id)
        else:
            if args.doc is None:
                raise ValueError("fill needs --doc")
            reqs = fill(json.loads(args.doc.read_text()), args.tab_id, tables)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(reqs, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
