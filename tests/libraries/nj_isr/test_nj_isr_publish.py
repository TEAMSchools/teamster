from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pytest

from teamster.libraries.nj_isr.drive import (
    FOLDER_MIME,
    SHEET_MIME,
    SHORTCUT_MIME,
    DriveFile,
)
from teamster.libraries.nj_isr.layout import IndexRow, OutputFile
from teamster.libraries.nj_isr.models import MissingFolderError
from teamster.libraries.nj_isr.publish import TAG_KEY, publish

NEWARK = "Newark Report Cards and Transcripts"
YEAR = "Spring 2026 NJSLA ISRs"
TRANSFER = "Transfer Out & Unmatched"
SHEET = "Newark NJSLA Reports Index - Spring 2026"
SHORTCUT = "00 - Find a student's NJSLA report - Spring 2026"

TEAM_PDF = "KIPP TEAM Academy - NJSLA Reports - Spring 2026.pdf"
TEAM_SCIENCE_PDF = "KIPP TEAM Academy - NJSLA Science Reports - Spring 2026.pdf"
SPARK_PDF = "SPARK Academy - NJSLA Reports - Spring 2026.pdf"
TRANSFER_PDF = "Newark Transfer Out & Unmatched - NJSLA Reports - Spring 2026.pdf"

TEAM_ID = 133570965
SPARK_ID = 73254


def output_file(schoolid: int | None, file_name: str) -> OutputFile:
    return OutputFile("Newark", schoolid, file_name, ())


team_file = output_file(TEAM_ID, TEAM_PDF)
team_science_file = output_file(TEAM_ID, TEAM_SCIENCE_PDF)
spark_file = output_file(SPARK_ID, SPARK_PDF)
transfer_file = output_file(None, TRANSFER_PDF)

PDFS = {
    f.file_name: Path(f"/unused/{f.file_name}")
    for f in (team_file, team_science_file, spark_file, transfer_file)
}

ROWS = {
    "Newark": [
        IndexRow(
            student="Adams, Al",
            student_number="1",
            grade="5",
            subject="ELA",
            where="KIPP TEAM Academy",
            last_spring_school="KIPP TEAM Academy",
            file_name=TEAM_PDF,
            page=1,
            note="",
        )
    ]
}

KW = {
    "program": "NJSLA",
    "admin": "Spring 2026",
    "tag": "2026_Spring_NJSLA",
    "ran_at": datetime(2026, 10, 19, 9, 30),
    "create_missing": False,
    "page_anchor": True,
    "allow_trash": False,
}
TRASH = {**KW, "allow_trash": True}


@dataclass
class Item:
    id: str
    name: str
    mime_type: str
    parent: str
    properties: dict[str, str]
    trashed: bool = False
    web_view_link: str = ""


ROOT_NAME = "Test root"


@dataclass
class FakeDrive:
    """In-memory Drive. The root folder is "root" and is not an item."""

    items: dict[str, Item] = field(default_factory=dict)
    writes: list[tuple[str, str]] = field(default_factory=list)
    sheets: dict[str, dict[str, list[list[str]]]] = field(default_factory=dict)
    _next_id: int = 0

    def _add(
        self,
        parent: str,
        name: str,
        mime_type: str,
        properties: Mapping[str, str] | None = None,
    ) -> Item:
        self._next_id += 1
        item_id = f"id{self._next_id}"
        item = Item(
            id=item_id,
            name=name,
            mime_type=mime_type,
            parent=parent,
            properties=dict(properties or {}),
            web_view_link=f"https://drive.test/{item_id}",
        )
        self.items[item_id] = item
        return item

    @staticmethod
    def _file(item: Item) -> DriveFile:
        return DriveFile(item.id, item.name, item.web_view_link)

    def _live_children(self, parent_id: str) -> list[Item]:
        return [
            i for i in self.items.values() if i.parent == parent_id and not i.trashed
        ]

    # DriveApi

    def get(self, file_id: str) -> DriveFile:
        if file_id == "root":
            return DriveFile("root", ROOT_NAME, "https://drive.test/root")

        if file_id not in self.items:
            raise MissingFolderError(f"Drive returned 404 for {file_id}")

        return self._file(self.items[file_id])

    def list_children(self, parent_id: str, mime_type: str) -> list[DriveFile]:
        return [
            self._file(i)
            for i in self._live_children(parent_id)
            if i.mime_type == mime_type
        ]

    def find_child(self, parent_id: str, name: str, mime_type: str) -> DriveFile | None:
        matches = [
            i
            for i in self._live_children(parent_id)
            if i.name == name and i.mime_type == mime_type
        ]

        if len(matches) > 1:
            raise MissingFolderError(f"{len(matches)} items named {name!r}")

        return self._file(matches[0]) if matches else None

    def create(
        self,
        parent_id: str,
        name: str,
        mime_type: str,
        *,
        media_path: Path | None = None,
        properties: Mapping[str, str] | None = None,
        shortcut_target: str | None = None,
    ) -> DriveFile:
        self.writes.append(("create", name))

        return self._file(self._add(parent_id, name, mime_type, properties))

    def update_media(self, file_id: str, media_path: Path) -> DriveFile:
        self.writes.append(("update_media", self.items[file_id].name))

        return self._file(self.items[file_id])

    def list_tagged(self, parent_id: str, key: str, value: str) -> list[DriveFile]:
        return [
            self._file(i)
            for i in self._live_children(parent_id)
            if i.properties.get(key) == value
        ]

    def trash(self, file_id: str) -> None:
        self.writes.append(("trash", self.items[file_id].name))
        self.items[file_id].trashed = True

    def readers(self, file_id: str) -> list[str]:
        return [f"reader: {self.get(file_id).name}"]

    def write_sheet(
        self, spreadsheet_id: str, tabs: Mapping[str, list[list[str]]]
    ) -> None:
        self.writes.append(("write_sheet", self.items[spreadsheet_id].name))
        self.sheets[spreadsheet_id] = dict(tabs)

    # assertions

    def _path(self, item: Item) -> str:
        parent = self.items.get(item.parent)

        return item.name if parent is None else f"{self._path(parent)}/{item.name}"

    def ids_by_path(self) -> dict[str, str]:
        return {self._path(i): i.id for i in self.items.values() if not i.trashed}

    def path_exists(self, path: str) -> bool:
        return path in self.ids_by_path()

    def named(self, name: str) -> list[Item]:
        return [i for i in self.items.values() if i.name == name and not i.trashed]

    def tag_of(self, name: str) -> dict[str, str]:
        return self.named(name)[0].properties

    def sheet_values(self, name: str) -> dict[str, list[list[str]]]:
        return self.sheets[self.named(name)[0].id]


def fake_drive_with_existing(*paths: str) -> FakeDrive:
    """Seeds folders under "root"; a repeated path adds a second leaf of that name."""
    drive = FakeDrive()

    for path in paths:
        parent = "root"
        *ancestors, leaf = path.split("/")

        for name in ancestors:
            found = drive.find_child(parent, name, FOLDER_MIME)
            parent = (found or drive._add(parent, name, FOLDER_MIME)).id

        drive._add(parent, leaf, FOLDER_MIME)

    return drive


def newark_drive() -> FakeDrive:
    return fake_drive_with_existing(
        NEWARK, f"{NEWARK}/TEAM Report Cards", f"{NEWARK}/SPARK Report Cards"
    )


def test_first_publish_builds_the_layout():
    drive = newark_drive()

    result = publish(drive, "root", [team_file, transfer_file], PDFS, ROWS, **KW)

    year = f"{NEWARK}/{YEAR}"
    team_year = f"{NEWARK}/TEAM Report Cards/{YEAR}"
    assert drive.path_exists(f"{year}/{SHEET}")
    assert drive.path_exists(f"{year}/{TRANSFER}/{TRANSFER_PDF}")
    assert drive.path_exists(f"{year}/{TRANSFER}/{SHORTCUT}")
    assert drive.path_exists(f"{team_year}/{TEAM_PDF}")
    assert drive.path_exists(f"{team_year}/{SHORTCUT}")
    assert drive.tag_of(TEAM_PDF) == {TAG_KEY: "2026_Spring_NJSLA"}
    assert drive.tag_of(SHEET) == {TAG_KEY: "2026_Spring_NJSLA"}
    assert drive.sheet_values(SHEET)["All reports"][5][0] == "Adams, Al"
    assert set(result.links) == {TEAM_PDF, TRANSFER_PDF}
    assert result.sheets == {"Newark": drive.named(SHEET)[0].web_view_link}
    assert result.readers == {"Newark": [f"reader: {YEAR}"]}
    assert result.trashed == []
    assert result.orphans_kept == []


def test_shortcuts_and_folders_are_not_tagged():
    drive = newark_drive()

    publish(drive, "root", [team_file, transfer_file], PDFS, ROWS, **KW)

    for item in drive.items.values():
        if item.mime_type in (FOLDER_MIME, SHORTCUT_MIME):
            assert item.properties == {}


def test_sheet_links_point_at_the_uploaded_pdf():
    drive = newark_drive()

    result = publish(drive, "root", [team_file], PDFS, ROWS, **KW)

    cell = drive.sheet_values(SHEET)["All reports"][5][6]
    assert result.links[TEAM_PDF] in cell
    assert cell.endswith('#page=1", "Open report")')


def test_rerun_keeps_every_file_id():
    drive = newark_drive()
    files = [team_file, spark_file, transfer_file]
    publish(drive, "root", files, PDFS, ROWS, **KW)
    before = drive.ids_by_path()

    publish(drive, "root", files, PDFS, ROWS, **KW)

    assert drive.ids_by_path() == before


def test_rerun_replaces_pdf_content_instead_of_duplicating():
    drive = newark_drive()
    publish(drive, "root", [team_file], PDFS, ROWS, **KW)
    drive.writes.clear()

    publish(drive, "root", [team_file], PDFS, ROWS, **KW)

    assert ("update_media", TEAM_PDF) in drive.writes
    assert ("create", TEAM_PDF) not in drive.writes
    assert len(drive.named(TEAM_PDF)) == 1


def test_rerun_without_allow_trash_keeps_and_lists_a_file_no_longer_produced():
    drive = newark_drive()
    publish(drive, "root", [team_file, team_science_file], PDFS, ROWS, **KW)
    drive.writes.clear()

    result = publish(drive, "root", [team_file], PDFS, ROWS, **KW)

    assert result.trashed == []
    assert result.orphans_kept == [TEAM_SCIENCE_PDF]
    assert len(drive.named(TEAM_SCIENCE_PDF)) == 1
    assert [w for w in drive.writes if w[0] == "trash"] == []


def test_rerun_with_allow_trash_trashes_a_file_no_longer_produced():
    drive = newark_drive()
    publish(drive, "root", [team_file, team_science_file], PDFS, ROWS, **KW)

    result = publish(drive, "root", [team_file], PDFS, ROWS, **TRASH)

    assert result.trashed == [TEAM_SCIENCE_PDF]
    assert result.orphans_kept == []
    assert drive.named(TEAM_SCIENCE_PDF) == []


def test_rerun_trashes_orphans_in_a_school_that_has_no_files_this_run():
    drive = newark_drive()
    publish(drive, "root", [team_file, spark_file, transfer_file], PDFS, ROWS, **KW)

    result = publish(drive, "root", [team_file, transfer_file], PDFS, ROWS, **TRASH)

    assert result.trashed == [SPARK_PDF]


def test_rerun_trashes_a_stale_transfer_file():
    drive = newark_drive()
    publish(drive, "root", [team_file, transfer_file], PDFS, ROWS, **KW)

    result = publish(drive, "root", [team_file], PDFS, ROWS, **TRASH)

    assert result.trashed == [TRANSFER_PDF]


def test_orphan_scan_leaves_untagged_files_sheet_and_shortcuts():
    drive = newark_drive()
    publish(drive, "root", [team_file, transfer_file], PDFS, ROWS, **KW)
    team_year = next(
        i.id
        for i in drive.items.values()
        if i.name == YEAR and "TEAM" in drive._path(i)
    )
    drive._add(team_year, "Staff notes.pdf", "application/pdf")

    result = publish(drive, "root", [team_file, transfer_file], PDFS, ROWS, **TRASH)

    assert result.trashed == []
    assert len(drive.named("Staff notes.pdf")) == 1
    assert len(drive.named(SHEET)) == 1
    assert len(drive.named(SHORTCUT)) == 2


def test_orphan_scan_ignores_a_configured_school_without_folders():
    drive = fake_drive_with_existing(NEWARK, f"{NEWARK}/TEAM Report Cards")

    result = publish(drive, "root", [team_file], PDFS, ROWS, **TRASH)

    assert result.trashed == []
    assert not any("SPARK" in drive._path(i) for i in drive.items.values())


def test_missing_school_folder_stops_before_any_write():
    drive = fake_drive_with_existing(NEWARK)

    with pytest.raises(MissingFolderError, match="TEAM Report Cards"):
        publish(drive, "root", [team_file], PDFS, ROWS, **KW)

    assert drive.writes == []


def test_missing_region_folder_stops_before_any_write():
    drive = fake_drive_with_existing()

    with pytest.raises(MissingFolderError, match=NEWARK):
        publish(drive, "root", [team_file], PDFS, ROWS, **KW)

    assert drive.writes == []


def test_every_problem_is_listed_in_one_error():
    drive = fake_drive_with_existing(NEWARK, f"{NEWARK}/TEAM Report Cards")

    with pytest.raises(MissingFolderError) as excinfo:
        publish(drive, "root", [team_file, spark_file], PDFS, ROWS, **KW)

    assert "SPARK Report Cards" in str(excinfo.value)
    assert "TEAM Report Cards" not in str(excinfo.value)

    drive = fake_drive_with_existing(NEWARK)

    with pytest.raises(MissingFolderError) as excinfo:
        publish(drive, "root", [team_file, spark_file], PDFS, ROWS, **KW)

    assert "SPARK Report Cards" in str(excinfo.value)
    assert "TEAM Report Cards" in str(excinfo.value)
    assert drive.writes == []


def test_duplicate_school_folder_name_stops_before_any_write():
    drive = fake_drive_with_existing(
        NEWARK, f"{NEWARK}/TEAM Report Cards", f"{NEWARK}/TEAM Report Cards"
    )

    with pytest.raises(MissingFolderError):
        publish(drive, "root", [team_file], PDFS, ROWS, **KW)

    assert drive.writes == []


def test_duplicate_region_folder_name_stops_before_any_write():
    drive = fake_drive_with_existing(NEWARK, NEWARK)

    with pytest.raises(MissingFolderError):
        publish(drive, "root", [team_file], PDFS, ROWS, **KW)

    assert drive.writes == []


def test_unconfigured_school_stops_before_any_write():
    drive = fake_drive_with_existing(NEWARK)

    with pytest.raises(MissingFolderError, match="999999"):
        publish(
            drive,
            "root",
            [output_file(999999, "X.pdf")],
            {"X.pdf": Path("x")},
            ROWS,
            **KW,
        )

    assert drive.writes == []


def test_create_missing_builds_folders_for_a_test_run():
    drive = fake_drive_with_existing()

    publish(drive, "root", [team_file], PDFS, ROWS, **{**KW, "create_missing": True})

    assert drive.path_exists(f"{NEWARK}/TEAM Report Cards")
    assert drive.path_exists(f"{NEWARK}/TEAM Report Cards/{YEAR}/{TEAM_PDF}")


def test_create_missing_refuses_a_root_holding_a_non_region_folder():
    drive = fake_drive_with_existing(NEWARK, "TEAM Report Cards")

    with pytest.raises(MissingFolderError) as excinfo:
        publish(
            drive, "root", [team_file], PDFS, ROWS, **{**KW, "create_missing": True}
        )

    assert (
        "--create-missing-folders is only for an empty test folder; the root holds "
        "'TEAM Report Cards'"
    ) in str(excinfo.value)
    assert NEWARK not in str(excinfo.value)
    assert drive.writes == []


def test_create_missing_allows_a_root_holding_only_region_folders():
    drive = fake_drive_with_existing(NEWARK, "Camden Report Cards and Transcripts")

    publish(drive, "root", [team_file], PDFS, ROWS, **{**KW, "create_missing": True})

    assert drive.path_exists(f"{NEWARK}/TEAM Report Cards/{YEAR}/{TEAM_PDF}")


def test_publish_reports_the_root_folder_and_its_readers():
    drive = newark_drive()

    result = publish(drive, "root", [team_file], PDFS, ROWS, **KW)

    assert result.root_name == ROOT_NAME
    assert result.root_readers == [f"reader: {ROOT_NAME}"]


def test_unreadable_root_stops_before_any_write():
    drive = newark_drive()

    with pytest.raises(MissingFolderError, match="--root-folder"):
        publish(drive, "not-shared", [team_file], PDFS, ROWS, **KW)

    assert drive.writes == []


def test_create_missing_still_stops_on_a_doubled_name():
    drive = fake_drive_with_existing(
        NEWARK, f"{NEWARK}/TEAM Report Cards", f"{NEWARK}/TEAM Report Cards"
    )

    with pytest.raises(MissingFolderError):
        publish(
            drive, "root", [team_file], PDFS, ROWS, **{**KW, "create_missing": True}
        )

    assert drive.writes == []


def test_sheet_is_found_again_and_rewritten_on_rerun():
    drive = newark_drive()
    publish(drive, "root", [team_file], PDFS, ROWS, **KW)
    sheet_id = drive.named(SHEET)[0].id
    drive.sheets.clear()

    publish(drive, "root", [team_file], PDFS, ROWS, **KW)

    assert [i.id for i in drive.named(SHEET)] == [sheet_id]
    assert drive.sheets[sheet_id]["All reports"][5][0] == "Adams, Al"


def test_index_sheet_mime_is_a_google_sheet():
    drive = newark_drive()

    publish(drive, "root", [team_file], PDFS, ROWS, **KW)

    assert drive.named(SHEET)[0].mime_type == SHEET_MIME


TEAM_YEAR = f"{NEWARK}/TEAM Report Cards/{YEAR}"


def test_duplicate_school_yearly_folder_stops_before_any_write():
    drive = fake_drive_with_existing(
        NEWARK, f"{NEWARK}/TEAM Report Cards", TEAM_YEAR, TEAM_YEAR
    )

    with pytest.raises(MissingFolderError, match=YEAR):
        publish(drive, "root", [team_file], PDFS, ROWS, **KW)

    assert drive.writes == []


def test_duplicate_region_yearly_folder_stops_before_any_write():
    drive = fake_drive_with_existing(
        NEWARK,
        f"{NEWARK}/TEAM Report Cards",
        f"{NEWARK}/{YEAR}",
        f"{NEWARK}/{YEAR}",
    )

    with pytest.raises(MissingFolderError, match=YEAR):
        publish(drive, "root", [team_file], PDFS, ROWS, **KW)

    assert drive.writes == []


def test_duplicate_transfer_folder_stops_before_any_write():
    drive = fake_drive_with_existing(
        NEWARK,
        f"{NEWARK}/TEAM Report Cards",
        f"{NEWARK}/{YEAR}/{TRANSFER}",
        f"{NEWARK}/{YEAR}/{TRANSFER}",
    )

    with pytest.raises(MissingFolderError, match=TRANSFER):
        publish(drive, "root", [team_file], PDFS, ROWS, **KW)

    assert drive.writes == []


def test_duplicate_shortcut_stops_before_any_write_on_a_rerun():
    drive = newark_drive()
    publish(drive, "root", [team_file], PDFS, ROWS, **KW)
    team_year_id = drive.ids_by_path()[TEAM_YEAR]
    drive._add(team_year_id, SHORTCUT, SHORTCUT_MIME)
    drive.writes.clear()

    with pytest.raises(MissingFolderError, match="Find a student"):
        publish(drive, "root", [team_file], PDFS, ROWS, **KW)

    assert drive.writes == []


def test_duplicate_yearly_folder_of_a_school_without_files_is_skipped():
    drive = fake_drive_with_existing(
        NEWARK,
        f"{NEWARK}/TEAM Report Cards",
        f"{NEWARK}/SPARK Report Cards/{YEAR}",
        f"{NEWARK}/SPARK Report Cards/{YEAR}",
    )

    result = publish(drive, "root", [team_file], PDFS, ROWS, **TRASH)

    assert result.trashed == []


def test_file_without_a_local_pdf_stops_before_any_write():
    drive = newark_drive()
    pdfs = {k: v for k, v in PDFS.items() if k != SPARK_PDF}

    with pytest.raises(MissingFolderError, match="SPARK Academy"):
        publish(drive, "root", [team_file, spark_file], pdfs, ROWS, **KW)

    assert drive.writes == []


class SheetWriteFails(RuntimeError):
    pass


def test_failed_sheet_write_leaves_nothing_trashed():
    drive = newark_drive()
    publish(drive, "root", [team_file, team_science_file], PDFS, ROWS, **KW)

    def fail(spreadsheet_id: str, tabs: Mapping[str, list[list[str]]]) -> None:
        raise SheetWriteFails

    drive.write_sheet = fail  # type: ignore[method-assign]
    drive.writes.clear()

    with pytest.raises(SheetWriteFails):
        publish(drive, "root", [team_file], PDFS, ROWS, **TRASH)

    assert [w for w in drive.writes if w[0] == "trash"] == []
    assert len(drive.named(TEAM_SCIENCE_PDF)) == 1
