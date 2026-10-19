from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from teamster.libraries.nj_isr.destinations import REGION_FOLDERS, SCHOOL_FOLDERS
from teamster.libraries.nj_isr.drive import (
    FOLDER_MIME,
    PDF_MIME,
    SHEET_MIME,
    SHORTCUT_MIME,
    DriveApi,
)
from teamster.libraries.nj_isr.layout import (
    IndexRow,
    OutputFile,
    index_sheet_name,
    sheet_tabs,
    shortcut_name,
    year_folder_name,
)
from teamster.libraries.nj_isr.match import TRANSFER_FOLDER
from teamster.libraries.nj_isr.models import MissingFolderError

TAG_KEY = "nj_isr_admin"


@dataclass(frozen=True)
class PublishResult:
    links: dict[str, str]  # file_name -> webViewLink
    sheets: dict[str, str]  # region -> Sheet webViewLink
    trashed: list[str]  # file names moved to the trash
    readers: dict[str, list[str]]  # region -> who can open the region's yearly folder


def _find_or_create_folder(api: DriveApi, parent_id: str, name: str) -> str:
    found = api.find_child(parent_id, name, FOLDER_MIME)

    if found is not None:
        return found.id

    return api.create(parent_id, name, FOLDER_MIME).id


def _lookup_folder(
    api: DriveApi,
    parent_id: str | None,
    name: str,
    *,
    create_missing: bool,
    problems: list[str],
    missing_message: str,
) -> tuple[str | None, bool]:
    """Read-only folder lookup. Returns (folder id, whether to create it later).

    A doubled name is always a problem. A missing name is a problem unless
    `create_missing` is set.
    """
    if parent_id is not None:
        try:
            found = api.find_child(parent_id, name, FOLDER_MIME)
        except MissingFolderError as e:
            problems.append(str(e))
            return None, False

        if found is not None:
            return found.id, False

    if create_missing:
        return None, True

    problems.append(missing_message)

    return None, False


def _resolve_folders(
    api: DriveApi,
    root_id: str,
    files: Sequence[OutputFile],
    *,
    create_missing: bool,
) -> tuple[dict[str, str], dict[tuple[str, int], str]]:
    """Find every region and school folder the files need, writing nothing.

    Raises one MissingFolderError naming every problem. With `create_missing`,
    a folder that does not exist is created afterward (after every lookup has
    passed); a name that matches 2 or more folders still raises.
    """
    problems: list[str] = []
    to_create_regions: list[str] = []
    to_create_schools: list[tuple[str, int]] = []
    region_ids: dict[str, str] = {}
    school_ids: dict[tuple[str, int], str] = {}

    regions = sorted({f.region for f in files})

    for region in regions:
        if region not in REGION_FOLDERS:
            problems.append(f"no region folder is configured for {region!r}")
            continue

        name = REGION_FOLDERS[region]
        folder_id, create = _lookup_folder(
            api,
            root_id,
            name,
            create_missing=create_missing,
            problems=problems,
            missing_message=f"Drive folder {name!r} not found under the root",
        )

        if folder_id is not None:
            region_ids[region] = folder_id
        elif create:
            to_create_regions.append(region)

    schools = sorted(
        {(f.region, f.schoolid) for f in files if f.schoolid is not None},
        key=lambda k: (k[0], k[1]),
    )

    for region, schoolid in schools:
        if region not in REGION_FOLDERS:
            continue

        if (region, schoolid) not in SCHOOL_FOLDERS:
            problems.append(f"no school folder is configured for {(region, schoolid)}")
            continue

        name = SCHOOL_FOLDERS[(region, schoolid)]
        folder_id, create = _lookup_folder(
            api,
            region_ids.get(region),
            name,
            create_missing=create_missing,
            problems=problems,
            missing_message=(
                f"Drive folder {name!r} not found in {REGION_FOLDERS[region]!r}"
            ),
        )

        if folder_id is not None:
            school_ids[(region, schoolid)] = folder_id
        elif create:
            to_create_schools.append((region, schoolid))

    if problems:
        raise MissingFolderError("; ".join(problems))

    for region in to_create_regions:
        region_ids[region] = api.create(root_id, REGION_FOLDERS[region], FOLDER_MIME).id

    for region, schoolid in to_create_schools:
        school_ids[(region, schoolid)] = api.create(
            region_ids[region], SCHOOL_FOLDERS[(region, schoolid)], FOLDER_MIME
        ).id

    return region_ids, school_ids


def _upload_pdf(api: DriveApi, folder_id: str, name: str, path: Path, tag: str) -> str:
    """Updates the tagged PDF of this name in place, or creates it. Returns its link."""
    existing = next(
        (f for f in api.list_tagged(folder_id, TAG_KEY, tag) if f.name == name), None
    )

    if existing is not None:
        return api.update_media(existing.id, path).web_view_link

    return api.create(
        folder_id,
        name,
        PDF_MIME,
        media_path=path,
        app_properties={TAG_KEY: tag},
    ).web_view_link


def _ensure_shortcut(api: DriveApi, folder_id: str, name: str, sheet_id: str) -> None:
    if api.find_child(folder_id, name, SHORTCUT_MIME) is None:
        api.create(folder_id, name, SHORTCUT_MIME, shortcut_target=sheet_id)


def _trash_orphans(
    api: DriveApi, folder_id: str, produced: set[str], tag: str, keep_id: str
) -> list[str]:
    trashed: list[str] = []

    for item in sorted(api.list_tagged(folder_id, TAG_KEY, tag), key=lambda f: f.name):
        if item.name in produced or item.id == keep_id:
            continue

        api.trash(item.id)
        trashed.append(item.name)

    return trashed


def publish(
    api: DriveApi,
    root_id: str,
    files: Sequence[OutputFile],
    pdf_paths: Mapping[str, Path],
    rows_by_region: Mapping[str, list[IndexRow]],
    *,
    program: str,
    admin: str,
    tag: str,
    ran_at: datetime,
    create_missing: bool,
    page_anchor: bool,
) -> PublishResult:
    """Puts the output files, their shortcuts, and each region's index in Drive.

    Layout: root / region folder / (yearly folder holding the index Sheet and
    the transfer folder) and root / region folder / school folder / yearly
    folder holding that school's PDFs and a shortcut to the Sheet.

    Every region and school folder lookup happens before the first write, so a
    missing or doubled folder name leaves Drive untouched. Files keep their IDs
    on a rerun: a tagged PDF or Sheet of the same name is updated in place.
    Only PDFs and Sheets are tagged, so the orphan scan never trashes anything
    else.
    """
    region_ids, school_ids = _resolve_folders(
        api, root_id, files, create_missing=create_missing
    )

    year_name = year_folder_name(program, admin)
    regions = sorted(region_ids)

    year_ids: dict[str, str] = {}
    transfer_ids: dict[str, str] = {}
    sheet_ids: dict[str, str] = {}
    links: dict[str, str] = {}
    sheets: dict[str, str] = {}

    for region in regions:
        year_id = _find_or_create_folder(api, region_ids[region], year_name)
        year_ids[region] = year_id
        transfer_ids[region] = _find_or_create_folder(api, year_id, TRANSFER_FOLDER)

        sheet_name = index_sheet_name(region, program, admin)
        sheet = next(
            (f for f in api.list_tagged(year_id, TAG_KEY, tag) if f.name == sheet_name),
            None,
        ) or api.create(year_id, sheet_name, SHEET_MIME, app_properties={TAG_KEY: tag})
        sheet_ids[region] = sheet.id
        sheets[region] = sheet.web_view_link

    school_year_ids: dict[tuple[str, int], str] = {}
    produced: dict[str, set[str]] = {}

    for file in files:
        if file.schoolid is None:
            folder_id = transfer_ids[file.region]
        else:
            key = (file.region, file.schoolid)

            if key not in school_year_ids:
                school_year_ids[key] = _find_or_create_folder(
                    api, school_ids[key], year_name
                )

            folder_id = school_year_ids[key]

        links[file.file_name] = _upload_pdf(
            api, folder_id, file.file_name, pdf_paths[file.file_name], tag
        )
        produced.setdefault(folder_id, set()).add(file.file_name)

    link_name = shortcut_name(program, admin)

    for (region, _schoolid), folder_id in school_year_ids.items():
        _ensure_shortcut(api, folder_id, link_name, sheet_ids[region])

    for region in regions:
        _ensure_shortcut(api, transfer_ids[region], link_name, sheet_ids[region])

    trashed: list[str] = []

    for region in regions:
        trashed.extend(
            _trash_orphans(
                api,
                transfer_ids[region],
                produced.get(transfer_ids[region], set()),
                tag,
                sheet_ids[region],
            )
        )

        configured = sorted(schoolid for r, schoolid in SCHOOL_FOLDERS if r == region)

        for schoolid in configured:
            key = (region, schoolid)
            folder_id = school_year_ids.get(key)

            if folder_id is None:
                try:
                    school = api.find_child(
                        region_ids[region], SCHOOL_FOLDERS[key], FOLDER_MIME
                    )
                    year = (
                        api.find_child(school.id, year_name, FOLDER_MIME)
                        if school is not None
                        else None
                    )
                except MissingFolderError:
                    continue

                if year is None:
                    continue

                folder_id = year.id

            trashed.extend(
                _trash_orphans(
                    api,
                    folder_id,
                    produced.get(folder_id, set()),
                    tag,
                    sheet_ids[region],
                )
            )

    for region in regions:
        api.write_sheet(
            sheet_ids[region],
            sheet_tabs(
                rows_by_region.get(region, []),
                links,
                region=region,
                program=program,
                admin=admin,
                ran_at=ran_at,
                page_anchor=page_anchor,
            ),
        )

    return PublishResult(
        links=links,
        sheets=sheets,
        trashed=trashed,
        readers={region: api.readers(year_ids[region]) for region in regions},
    )
