from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from teamster.libraries.nj_isr.destinations import REGION_FOLDERS, SCHOOL_FOLDERS
from teamster.libraries.nj_isr.drive import (
    FOLDER_MIME,
    PDF_MIME,
    SHEET_MIME,
    SHORTCUT_MIME,
    DriveApi,
    DriveFile,
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

SchoolKey = tuple[str, int]  # (region, PowerSchool schoolid)


@dataclass(frozen=True)
class PublishResult:
    links: dict[str, str]  # file_name -> webViewLink
    sheets: dict[str, str]  # region -> Sheet webViewLink
    trashed: list[str]  # file names moved to the trash
    readers: dict[str, list[str]]  # region -> who can open the region's yearly folder
    root_name: str  # name of the --root-folder folder
    root_readers: list[str]  # who can open the root folder


@dataclass
class _Plan:
    """What Drive already holds, found with reads only.

    Every `find_child` call in a run happens while building this, because the
    real client raises when a name matches 2 or more items.
    """

    regions: list[str]
    root_name: str = ""
    root_readers: list[str] = field(default_factory=list)
    region_ids: dict[str, str] = field(default_factory=dict)
    school_ids: dict[SchoolKey, str] = field(default_factory=dict)
    year_ids: dict[str, str] = field(default_factory=dict)
    transfer_ids: dict[str, str] = field(default_factory=dict)
    school_year_ids: dict[SchoolKey, str] = field(default_factory=dict)
    shortcut_folders: set[str] = field(default_factory=set)
    missing_regions: list[str] = field(default_factory=list)
    missing_schools: list[SchoolKey] = field(default_factory=list)


def _lookup(
    api: DriveApi,
    parent_id: str | None,
    name: str,
    mime_type: str,
    problems: list[str] | None,
) -> DriveFile | None:
    """Read-only lookup. A doubled name goes to `problems`, or is skipped if None."""
    if parent_id is None:
        return None

    try:
        return api.find_child(parent_id, name, mime_type)
    except MissingFolderError as e:
        if problems is not None:
            problems.append(str(e))

        return None


def _plan(
    api: DriveApi,
    root_id: str,
    files: Sequence[OutputFile],
    pdf_paths: Mapping[str, Path],
    *,
    year_name: str,
    shortcut: str,
    create_missing: bool,
) -> _Plan:
    """Read everything the run depends on, writing nothing.

    Raises a MissingFolderError at once when the root cannot be read.
    Otherwise raises one MissingFolderError naming every problem: a missing
    local PDF, a region or school folder that is not configured, missing, or
    doubled (a missing one is allowed with `create_missing`), and any doubled
    name among the yearly folders, transfer folders, and shortcuts the run
    will use. `create_missing` also refuses a root that holds any folder other
    than a region folder, because it is only for an empty test folder: on the
    real root, a missing or misnamed school folder must stop the run.
    """
    problems: list[str] = []
    plan = _Plan(regions=sorted({f.region for f in files}))

    try:
        plan.root_name = api.get(root_id).name
    except MissingFolderError as e:
        raise MissingFolderError(f"cannot open the --root-folder link: {e}") from e

    plan.root_readers = api.readers(root_id)

    if create_missing:
        region_names = set(REGION_FOLDERS.values())
        for name in sorted(
            {f.name for f in api.list_children(root_id, FOLDER_MIME)} - region_names
        ):
            problems.append(
                "--create-missing-folders is only for an empty test folder; "
                f"the root holds {name!r}"
            )

    for name in sorted({f.file_name for f in files if f.file_name not in pdf_paths}):
        problems.append(f"no local PDF was given for {name!r}")

    for region in plan.regions:
        if region not in REGION_FOLDERS:
            problems.append(f"no region folder is configured for {region!r}")
            continue

        name = REGION_FOLDERS[region]
        count = len(problems)
        found = _lookup(api, root_id, name, FOLDER_MIME, problems)

        if found is not None:
            plan.region_ids[region] = found.id
        elif len(problems) == count:
            if create_missing:
                plan.missing_regions.append(region)
            else:
                problems.append(f"Drive folder {name!r} not found under the root")

    needed = sorted({(f.region, f.schoolid) for f in files if f.schoolid is not None})

    for region, schoolid in needed:
        if region not in REGION_FOLDERS:
            continue

        if (region, schoolid) not in SCHOOL_FOLDERS:
            problems.append(f"no school folder is configured for {(region, schoolid)}")
            continue

        name = SCHOOL_FOLDERS[(region, schoolid)]
        count = len(problems)
        found = _lookup(api, plan.region_ids.get(region), name, FOLDER_MIME, problems)

        if found is not None:
            plan.school_ids[(region, schoolid)] = found.id
        elif len(problems) == count:
            if create_missing:
                plan.missing_schools.append((region, schoolid))
            else:
                problems.append(
                    f"Drive folder {name!r} not found in {REGION_FOLDERS[region]!r}"
                )

    for region, region_id in plan.region_ids.items():
        year = _lookup(api, region_id, year_name, FOLDER_MIME, problems)

        if year is None:
            continue

        plan.year_ids[region] = year.id
        transfer = _lookup(api, year.id, TRANSFER_FOLDER, FOLDER_MIME, problems)

        if transfer is not None:
            plan.transfer_ids[region] = transfer.id

    for key, school_id in plan.school_ids.items():
        year = _lookup(api, school_id, year_name, FOLDER_MIME, problems)

        if year is not None:
            plan.school_year_ids[key] = year.id

    # Schools with no file this run still get an orphan scan. A missing or
    # doubled folder there is skipped, never an error.
    for region, region_id in plan.region_ids.items():
        for key in sorted(k for k in SCHOOL_FOLDERS if k[0] == region):
            if key in plan.school_ids or key in needed:
                continue

            school = _lookup(api, region_id, SCHOOL_FOLDERS[key], FOLDER_MIME, None)
            year = _lookup(
                api, school.id if school else None, year_name, FOLDER_MIME, None
            )

            if year is not None:
                plan.school_year_ids[key] = year.id

    shortcut_parents = [
        *plan.transfer_ids.values(),
        *(plan.school_year_ids[key] for key in needed if key in plan.school_year_ids),
    ]

    for folder_id in shortcut_parents:
        if _lookup(api, folder_id, shortcut, SHORTCUT_MIME, problems) is not None:
            plan.shortcut_folders.add(folder_id)

    if problems:
        raise MissingFolderError("; ".join(problems))

    return plan


def _ensure_folder(
    api: DriveApi, parent_id: str, name: str, known_id: str | None
) -> str:
    """Returns the folder the plan found, or creates it."""
    return known_id or api.create(parent_id, name, FOLDER_MIME).id


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
        properties={TAG_KEY: tag},
    ).web_view_link


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

    Every lookup that can fail happens before the first write: a missing or
    doubled name, or a missing local PDF, leaves Drive untouched. Files keep
    their IDs on a rerun: a tagged PDF or Sheet of the same name is updated in
    place. The Sheet is written before orphans are trashed, so a failed Sheet
    write leaves stale files rather than index links to trashed ones. Only PDFs
    and Sheets are tagged, so the orphan scan never trashes anything else.
    """
    year_name = year_folder_name(program, admin)
    link_name = shortcut_name(program, admin)

    plan = _plan(
        api,
        root_id,
        files,
        pdf_paths,
        year_name=year_name,
        shortcut=link_name,
        create_missing=create_missing,
    )

    region_ids = dict(plan.region_ids)
    school_ids = dict(plan.school_ids)

    for region in plan.missing_regions:
        region_ids[region] = api.create(root_id, REGION_FOLDERS[region], FOLDER_MIME).id

    for key in plan.missing_schools:
        school_ids[key] = api.create(
            region_ids[key[0]], SCHOOL_FOLDERS[key], FOLDER_MIME
        ).id

    regions = sorted(region_ids)
    year_ids: dict[str, str] = {}
    transfer_ids: dict[str, str] = {}
    sheet_ids: dict[str, str] = {}
    sheets: dict[str, str] = {}

    for region in regions:
        year_id = _ensure_folder(
            api, region_ids[region], year_name, plan.year_ids.get(region)
        )
        year_ids[region] = year_id
        transfer_ids[region] = _ensure_folder(
            api, year_id, TRANSFER_FOLDER, plan.transfer_ids.get(region)
        )

        sheet_name = index_sheet_name(region, program, admin)
        sheet = next(
            (f for f in api.list_tagged(year_id, TAG_KEY, tag) if f.name == sheet_name),
            None,
        ) or api.create(year_id, sheet_name, SHEET_MIME, properties={TAG_KEY: tag})
        sheet_ids[region] = sheet.id
        sheets[region] = sheet.web_view_link

    school_year_ids = dict(plan.school_year_ids)
    received: dict[SchoolKey, str] = {}
    produced: dict[str, set[str]] = {}
    links: dict[str, str] = {}

    for file in files:
        if file.schoolid is None:
            folder_id = transfer_ids[file.region]
        else:
            key = (file.region, file.schoolid)

            if key not in school_year_ids:
                school_year_ids[key] = api.create(
                    school_ids[key], year_name, FOLDER_MIME
                ).id

            folder_id = received[key] = school_year_ids[key]

        links[file.file_name] = _upload_pdf(
            api, folder_id, file.file_name, pdf_paths[file.file_name], tag
        )
        produced.setdefault(folder_id, set()).add(file.file_name)

    shortcut_targets = [
        (folder_id, sheet_ids[key[0]]) for key, folder_id in received.items()
    ] + [(transfer_ids[region], sheet_ids[region]) for region in regions]

    for folder_id, sheet_id in shortcut_targets:
        if folder_id not in plan.shortcut_folders:
            api.create(folder_id, link_name, SHORTCUT_MIME, shortcut_target=sheet_id)

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

    trashed: list[str] = []

    for region in regions:
        scan = [transfer_ids[region]] + [
            folder_id
            for (r, _schoolid), folder_id in sorted(school_year_ids.items())
            if r == region
        ]

        for folder_id in scan:
            trashed.extend(
                _trash_orphans(
                    api,
                    folder_id,
                    produced.get(folder_id, set()),
                    tag,
                    sheet_ids[region],
                )
            )

    return PublishResult(
        links=links,
        sheets=sheets,
        trashed=trashed,
        readers={region: api.readers(year_ids[region]) for region in regions},
        root_name=plan.root_name,
        root_readers=plan.root_readers,
    )
