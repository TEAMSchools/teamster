# NJ ISR Split and Regional Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** A yearly command that splits the state's NJ ISR PDFs by each student's
current school, files leavers and unmatched records in a regional
`Transfer Out & Unmatched` folder, and writes one index Google Sheet per region.

**Architecture:** A pure-Python library at `src/teamster/libraries/nj_isr/`, run
as `uv run python -m teamster.libraries.nj_isr`. Pure modules (segment, match,
layout) hold every decision and are unit-tested on synthetic text. Thin IO
modules read PDFs, query BigQuery, and call Drive and Sheets. Drive calls run as
the user through a separate `gcloud` sign-in; BigQuery uses the Codespace's
default credentials.

**Tech Stack:** Python 3.13, `pypdfium2` (read text), `pypdf` (write PDFs),
`google-cloud-bigquery`, `google-api-python-client` (Drive v3, Sheets v4),
`google-auth`, pytest.

**Spec:** `docs/superpowers/specs/2026-10-19-nj-isr-split-and-index-design.md`

## Global Constraints

- The repo is public. Never commit a Drive folder ID, file ID, or link key. The
  root folder link arrives as a runtime argument.
- No student-level value enters git, GitHub, or a test. Tests use invented
  names, IDs, and dates.
- The index never shows a portal access code, date of birth, state ID, or score.
- The command never adds, removes, or changes Drive sharing.
- Any failed check stops the run before the first Drive write.
- An uncertain match goes to `Transfer Out & Unmatched`, never to a guessed
  school.
- Read page text with `pypdfium2`; write PDFs with `pypdf`. Never PyMuPDF
  (AGPL).
- Cut pages from the state's file straight into each output. Never build one PDF
  per student and merge them.
- Every Drive API call passes `supportsAllDrives=True`.
- Footer regex, verbatim: `(\d{4})\.(\1_\d{3})\.(\d+)`, no leading word
  boundary.
- `<worktree>` means
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-nj-isr-split-index`.
  `<scratchpad>` means the session scratchpad directory. Student data lives only
  there or under `.claude/scratch/`.
- Run everything with `uv run`. Run tests from the worktree:
  `cd <worktree> && uv run pytest <path> -v`.
- Names use plain words. Exact names, built from `program` (`NJSLA`), `admin`
  (`Spring 2026`), and `region`:
  - yearly folder: `{admin} {program} ISRs`, for example
    `Spring 2026 NJSLA ISRs`
  - transfer folder: `Transfer Out & Unmatched`
  - index Sheet: `{region} {program} Reports Index - {admin}`
  - shortcut: `00 - Find a student's {program} report - {admin}`
  - school file: `{school_name} - {report_label} - {admin}.pdf`
  - transfer file:
    `{region} Transfer Out & Unmatched - {report_label} - {admin}.pdf`
  - `report_label`: `NJSLA Reports` (Combined), `NJSLA Science Reports`
    (Single), `NJGPA Reports` (any NJGPA file)
- Drive tag: `appProperties` key `nj_isr_admin`, value
  `{year}_{season}_{program}`, for example `2026_Spring_NJSLA`.

## Review Focus

1. Names with apostrophes, accents, hyphens, or several parts (`O'NEIL`,
   `GARCÍA-LOPEZ`, `DE LA CRUZ`) must confirm against PowerSchool. Test in
   Task 3.
2. A Drive name containing an apostrophe must not break the Drive search query.
   Test in Task 6.
3. A record with no printed birth date, or with no subject on any page (a "not
   tested" layout), must route to Unmatched or show `See report`, never crash.
   Tests in Tasks 2 and 4.
4. A school folder that is missing, or that has 2 folders with the same name,
   must stop the run before any write. Test in Task 7.
5. PowerSchool `schoolid` values repeat across regions (Paterson uses `2`), so
   school folders key on `(region, schoolid)`. Test in Task 3.

---

### Task 1: Prove the personal Google sign-in

No code is committed in this task. It retires the biggest risk first. The user
signs in, because the sign-in opens a browser and needs the user.

**Files:**

- Create (scratchpad only, never committed): `auth_check.py` in the session
  scratchpad.

- [ ] **Step 1: Check the `gcloud` flags**

Run:
`/usr/local/share/google-cloud-sdk/bin/gcloud auth application-default login --help | rg -n 'no-launch-browser|no-browser|scopes'`
Expected: both `--scopes` and a no-browser flag are listed. Use the flag the
help text names in Step 2.

- [ ] **Step 2: Ask the user to sign in, in their own terminal**

Give the user this command. It keeps the sign-in in its own folder, so the
Codespace's default credentials stay untouched:

```bash
CLOUDSDK_CONFIG=~/.config/teamster/nj-isr-gcloud \
  /usr/local/share/google-cloud-sdk/bin/gcloud auth application-default login \
  --no-launch-browser \
  --scopes=openid,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive
CLOUDSDK_CONFIG=~/.config/teamster/nj-isr-gcloud \
  /usr/local/share/google-cloud-sdk/bin/gcloud auth application-default set-quota-project teamster-332318
```

Expected: "Credentials saved to file". If Google shows "This app is blocked",
STOP and report to the user. The fallback, a desktop sign-in client in the
`teamster-332318` project, needs the data engineer, and changes Task 6's
`load_user_credentials`.

- [ ] **Step 3: Ask the user for a test folder link**

The user makes an empty folder in their own My Drive, for example `NJ ISR test`,
and pastes its link.

- [ ] **Step 4: Write and run the scratch check**

The script loads `application_default_credentials.json` from
`~/.config/teamster/nj-isr-gcloud` with `google.auth.load_credentials_from_file`
and the Drive scope, then in the test folder: creates a text file, updates its
content, confirms the file ID did not change, and moves it to the trash. Keep
the file name out of the Bash command line; a hook blocks credential paths
there.

Run: `uv run python -I <scratchpad>/auth_check.py <test-folder-id>` Expected:
`create ok`, `update ok (same id)`, `trash ok`. A 403 that names the Drive API
means the API is off in `teamster-332318`; report it to the user.

- [ ] **Step 5: Record the result**

Add one line to the task ledger: the sign-in works, or which step failed.

---

### Task 2: Package, models, and page segmentation

**Files:**

- Modify: `pyproject.toml`, `uv.lock` (add `pypdfium2`)
- Create: `src/teamster/libraries/nj_isr/__init__.py` (empty)
- Create: `src/teamster/libraries/nj_isr/models.py`
- Create: `src/teamster/libraries/nj_isr/segment.py`
- Test: `tests/libraries/nj_isr/test_nj_isr_segment.py`

**Interfaces:**

- Produces, in `models.py`:

```python
class IsrFormatError(ValueError): ...
class MissingFolderError(RuntimeError): ...

@dataclass(frozen=True)
class SourceFile:
    path: Path
    year: int                 # 2026
    season: str               # "Spring"
    district: str             # "7325"
    school_code: str          # "965"
    program: str              # "NJSLA" | "NJGPA"
    variant: str              # "Combined" | "Single" | ""
    reissue_date: date | None # from a trailing _MMDDYY

@dataclass(frozen=True)
class Record:
    source: SourceFile
    seq: int
    page_start: int           # 1-based, inclusive, in the source file
    page_end: int
    state_id: str
    printed_name: str         # "ALEX B. RIVERA", "" if absent
    printed_dob: date | None
    grade: int | None
    subjects: tuple[str, ...] # ordered subset of ("ELA", "Math", "Science")
    not_tested: bool

    @property
    def page_count(self) -> int: ...
```

- Produces, in `segment.py`:
  - `FOOTER_RE`, `parse_source_filename(path: Path) -> SourceFile | None`
    (returns `None` for `Labels` files and names that do not match)
  - `segment_pages(source: SourceFile, pages: list[str]) -> list[Record]`
  - `scan_folder(input_dir: Path, read_pages: Callable[[Path], list[str]]) -> list[Record]`
    (sorted by filename; raises `IsrFormatError` if files mix programs)
  - `apply_corrections(records: Sequence[Record]) -> tuple[list[Record], list[Record], list[Record]]`
    returning `(kept, replaced_originals, unpaired_corrections)`
  - `find_duplicate_state_ids(records: Sequence[Record]) -> list[Record]`

- [ ] **Step 1: Add the dependency**

Run:
`uv --directory /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-nj-isr-split-index add pypdfium2`
Expected: `pyproject.toml` lists `pypdfium2` and `uv.lock` changes.

- [ ] **Step 2: Write the failing tests**

Build synthetic pages with a helper in the test file. Each Combined record is 4
pages. Page 1 ends with the access code glued to the footer token. Pages 2 to 4
carry
`{name}\n ENROLLED GRADE: {grade}\nStudent ID:\n{sid}\nDate of Birth:\n{dob}`.
Page 2 names `English Language Arts`, page 3 `Mathematics`, and page 4 ends with
the footer token.

```python
def test_parse_source_filename():
    s = parse_source_filename(Path("2026_Spring_7325-965_ISR_SLA_Combined.pdf"))
    assert (s.year, s.season, s.district, s.school_code) == (2026, "Spring", "7325", "965")
    assert (s.program, s.variant, s.reissue_date) == ("NJSLA", "Combined", None)
    r = parse_source_filename(Path("2026_Spring_1799-111_ISR_SLA_Combined_100226.pdf"))
    assert r.reissue_date == date(2026, 10, 2)
    g = parse_source_filename(Path("2026_Spring_7325-965_ISR_GPA.pdf"))
    assert (g.program, g.variant) == ("NJGPA", "")
    assert parse_source_filename(Path("2026_Spring_7325-965_Labels_SLA.pdf")) is None

def test_segment_two_combined_records():
    recs = segment_pages(SRC, record(1, "1000000001") + record(2, "1000000002"))
    assert [(r.seq, r.page_start, r.page_end) for r in recs] == [(1, 1, 4), (2, 5, 8)]
    assert recs[0].state_id == "1000000001"
    assert recs[0].printed_name == "ALEX B. RIVERA"
    assert recs[0].printed_dob == date(2015, 3, 4)
    assert recs[0].grade == 5
    assert recs[0].subjects == ("ELA", "Math")

def test_footer_glued_to_code_ending_in_digits():
    recs = segment_pages(SRC, record(1, "1000000001", code="cc5787"))
    assert recs[0].seq == 1

def test_footer_on_every_page_njgpa_style():
    recs = segment_pages(SRC, njgpa_record(1, "1000000001"))  # 2 pages, token on both
    assert (recs[0].page_start, recs[0].page_end) == (1, 2)

def test_missing_dob_and_subjects_do_not_fail():
    recs = segment_pages(SRC, record(1, "1000000001", dob=None, subjects=()))
    assert recs[0].printed_dob is None
    assert recs[0].subjects == ()

@pytest.mark.parametrize("pages, message", [
    (record(1, "1") + record(3, "2"), "seq"),               # gap
    (record(1, "1", district="1799"), "district"),          # footer != filename
    (record(1, "1")[:3] + ["no footer"] + record(2, "2"), "page"),  # orphan page
    (record(1, "1000000001", extra_sid="1000000009"), "state ID"),   # 2 IDs
])
def test_segment_stops_on_bad_structure(pages, message):
    with pytest.raises(IsrFormatError, match=message):
        segment_pages(SRC, pages)

def test_apply_corrections():
    orig = rec(state_id="1000000001", file="2026_Spring_7325-965_ISR_SLA_Combined.pdf")
    other = rec(state_id="1000000002", file="2026_Spring_7325-965_ISR_SLA_Combined.pdf")
    fix = rec(state_id="1000000001", file="2026_Spring_7325-965_ISR_SLA_Combined_100226.pdf")
    late = rec(state_id="1000000001", file="2026_Spring_7325-965_ISR_SLA_Combined_101526.pdf")
    stray = rec(state_id="1000000003", file="2026_Spring_7325-965_ISR_SLA_Combined_100226.pdf")
    kept, replaced, unpaired = apply_corrections([orig, other, fix, late, stray])
    assert late in kept and fix not in kept and orig not in kept and other in kept
    assert replaced == [orig, fix]
    assert unpaired == [stray] and stray in kept

def test_duplicate_state_ids_are_kept_and_reported():
    a, b = rec(state_id="1000000001", seq=1), rec(state_id="1000000001", seq=2)
    assert find_duplicate_state_ids([a, b]) == [a, b]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/libraries/nj_isr/test_nj_isr_segment.py -v` Expected:
FAIL with `ModuleNotFoundError: No module named 'teamster.libraries.nj_isr'`

- [ ] **Step 4: Implement `models.py` and `segment.py`**

Segmentation rule: a page's footer token names its record. A page without a
token belongs to the record whose tokens surround it with the same `seq`; any
other footer-less page raises `IsrFormatError` naming the page. Field regexes,
applied to the record's joined text:

- state ID: `Student ID:\s*(\d{10})` (exactly 1 distinct value, else error)
- birth date: `Date of Birth:\s*(\d{2}/\d{2}/\d{2})`, parsed with `%m/%d/%y`
- grade: `ENROLLED GRADE:\s*(\d+)`
- printed name: the line right before ` ENROLLED GRADE:`,
  `\n([^\n]+)\n\s*ENROLLED GRADE:`
- subjects: `ELA` if `English Language Arts` appears, `Math` if `Mathematics`,
  `Science` if `Science`
- `not_tested`: `NOT TESTED` appears, case-insensitive

Corrections replace every non-correction record with the same
`(district, program, variant, state_id)`. The latest `reissue_date` wins, and
older corrections join `replaced`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/libraries/nj_isr/test_nj_isr_segment.py -v` Expected:
PASS

- [ ] **Step 6: Commit**

```bash
git -C <worktree> add pyproject.toml uv.lock src/teamster/libraries/nj_isr tests/libraries/nj_isr
git -C <worktree> commit -m "feat(nj_isr): segment state ISR PDFs into student records"
```

---

### Task 3: Match, confirm, and route

**Files:**

- Create: `src/teamster/libraries/nj_isr/match.py`
- Create: `src/teamster/libraries/nj_isr/destinations.py`
- Create: `src/teamster/libraries/nj_isr/warehouse.py`
- Test: `tests/libraries/nj_isr/test_nj_isr_match.py`

**Interfaces:**

- Consumes: `Record`, `SourceFile` (Task 2).
- Produces, in `match.py`:

```python
TRANSFER_FOLDER = "Transfer Out & Unmatched"

@dataclass(frozen=True)
class Enrollment:
    region: str
    schoolid: int
    school_name: str

@dataclass(frozen=True)
class Student:
    student_number: int
    last_name: str
    first_name: str
    dob: date | None
    current: Enrollment | None
    last_spring_school: str | None

@dataclass(frozen=True)
class Resolution:
    student: Student | None
    reason: str  # "matched" | "no_candidate" | "failed_confirmation" | "source_conflict"

@dataclass(frozen=True)
class Placement:
    record: Record
    resolution: Resolution
    region: str            # region of the destination folder
    schoolid: int | None   # None means the region's transfer folder
    where: str             # school_name, or TRANSFER_FOLDER

def last_name_matches(printed_name: str, ps_last_name: str) -> bool
def confirm(record: Record, student: Student) -> bool
def resolve(record: Record, crosswalk: Mapping[str, set[int]],
            by_state_id: Mapping[str, set[int]],
            students: Mapping[int, Student]) -> Resolution
def place(record: Record, resolution: Resolution, testing_region: str) -> Placement
```

- Produces, in `destinations.py`:
  - `REGION_BY_DISTRICT = {"7325": "Newark", "1799": "Camden", "7899": "Paterson"}`
  - `REGION_FOLDERS = {"Newark": "Newark Report Cards and Transcripts", "Camden": "Camden Report Cards and Transcripts", "Paterson": "Paterson Report Cards and Transcripts"}`
  - `SCHOOL_FOLDERS: dict[tuple[str, int], str]`, exactly:

| Key                     | Folder name                             |
| ----------------------- | --------------------------------------- |
| `("Newark", 73258)`     | `BOLD Report Cards`                     |
| `("Newark", 732513)`    | `Justice Report Cards`                  |
| `("Newark", 73257)`     | `Life Report Cards`                     |
| `("Newark", 73253)`     | `NCA Report Cards`                      |
| `("Newark", 732511)`    | `Lab Report Cards`                      |
| `("Newark", 732514)`    | `Purpose Report Cards`                  |
| `("Newark", 73252)`     | `Rise Report Cards`                     |
| `("Newark", 73254)`     | `SPARK Report Cards`                    |
| `("Newark", 73256)`     | `Seek Report Cards`                     |
| `("Newark", 133570965)` | `TEAM Report Cards`                     |
| `("Newark", 73255)`     | `THRIVE Report Cards`                   |
| `("Newark", 73259)`     | `KURA Report Cards`                     |
| `("Camden", 179901)`    | `LSP Report Cards`                      |
| `("Camden", 179902)`    | `LSM Report Cards`                      |
| `("Camden", 179903)`    | `Hatch Report Cards`                    |
| `("Camden", 179904)`    | `KHS Report Cards`                      |
| `("Camden", 179905)`    | `Sumner Report Cards`                   |
| `("Paterson", 1234)`    | `Paterson Prep Elementary Report Cards` |
| `("Paterson", 2)`       | `Paterson Prep Middle Report Cards`     |

- Produces, in `warehouse.py`:
  - `load_crosswalk(client: bigquery.Client, admin_academic_year: int) -> dict[str, set[int]]`
  - `load_students(client: bigquery.Client, school_year: int) -> tuple[dict[int, Student], dict[str, set[int]]]`
    returning `(students, by_state_id)`

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("printed, ps_last, expected", [
    ("SEAN P. O'NEIL", "O'Neil", True),
    ("ANA GARCÍA-LOPEZ", "Garcia Lopez", True),
    ("JOSE DE LA CRUZ", "De La Cruz", True),
    ("MARIA LOPEZ", "Garcia-Lopez", True),     # 1 part of a multi-part name
    ("BOBBY SMITH", "Smith", True),            # first names never compared
    ("ALEX RIVERA", "Jones", False),
])
def test_last_name_matches(printed, ps_last, expected):
    assert last_name_matches(printed, ps_last) is expected

def test_resolve_crosswalk_confirmed():
    r = resolve(rec(sid="1000000001"), {"1000000001": {101}}, {}, {101: alex})
    assert (r.reason, r.student) == ("matched", alex)

def test_resolve_wrong_dob_is_failed_confirmation():
    r = resolve(rec(sid="1000000001", dob=date(2015, 3, 5)), {"1000000001": {101}}, {}, {101: alex})
    assert (r.reason, r.student) == ("failed_confirmation", None)

def test_resolve_missing_dob_is_failed_confirmation():
    r = resolve(rec(sid="1000000001", dob=None), {"1000000001": {101}}, {}, {101: alex})
    assert r.reason == "failed_confirmation"

def test_resolve_conflict_picks_the_one_that_confirms():
    r = resolve(rec(sid="1000000001"), {"1000000001": {101}}, {"1000000001": {202}},
                {101: alex, 202: someone_else})
    assert r.student == alex

def test_resolve_conflict_neither_confirms():
    r = resolve(rec(sid="1000000001"), {"1000000001": {303}}, {"1000000001": {202}},
                {303: stranger, 202: someone_else})
    assert (r.reason, r.student) == ("source_conflict", None)

def test_resolve_ambiguous_crosswalk_falls_back_to_state_id():
    r = resolve(rec(sid="1000000001"), {"1000000001": {101, 404}}, {"1000000001": {101}}, {101: alex})
    assert r.student == alex

def test_resolve_no_candidate():
    assert resolve(rec(sid="1000000001"), {}, {}, {}).reason == "no_candidate"

def test_place_current_school_in_another_region():
    s = replace(alex, current=Enrollment("Paterson", 2, "Paterson Prep Middle School"))
    p = place(rec(), Resolution(s, "matched"), testing_region="Newark")
    assert (p.region, p.schoolid, p.where) == ("Paterson", 2, "Paterson Prep Middle School")

def test_place_not_enrolled_goes_to_testing_region_transfer():
    s = replace(alex, current=None)
    p = place(rec(), Resolution(s, "matched"), testing_region="Camden")
    assert (p.region, p.schoolid, p.where) == ("Camden", None, TRANSFER_FOLDER)

def test_place_unmatched_goes_to_transfer():
    p = place(rec(), Resolution(None, "no_candidate"), testing_region="Newark")
    assert (p.region, p.where) == ("Newark", TRANSFER_FOLDER)

def test_school_folders_key_on_region_and_schoolid():
    assert SCHOOL_FOLDERS[("Paterson", 2)] == "Paterson Prep Middle Report Cards"
    assert all(len(k) == 2 for k in SCHOOL_FOLDERS)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/libraries/nj_isr/test_nj_isr_match.py -v` Expected:
FAIL with `ModuleNotFoundError` for `teamster.libraries.nj_isr.match`

- [ ] **Step 3: Implement `match.py` and `destinations.py`**

`last_name_matches`: normalize both sides with NFKD, drop combining marks,
casefold, delete apostrophes (`'` and `’`), and split on whitespace, hyphens,
and periods. True when any PowerSchool part of 2 or more letters is among the
printed tokens. `confirm` requires `record.printed_dob == student.dob` (not
`None`) and `last_name_matches`.

`resolve`: candidate 1 comes from `crosswalk` when it holds exactly 1 number.
Candidate 2 comes from `by_state_id` when it holds exactly 1. If both exist and
differ, confirm each: exactly 1 passing wins, else `source_conflict`. If 1
candidate exists, or both are equal, confirm it: pass is `matched`, fail is
`failed_confirmation`. If none exists, `no_candidate`.

- [ ] **Step 4: Implement `warehouse.py`**

`load_crosswalk` runs, with `@admin_academic_year` as a query parameter:

```sql
select distinct cast(state_student_id as string) as state_id, student_number,
from `teamster-332318.kipptaf_cambium.int_cambium__all_assessments`
where academic_year = @admin_academic_year and period = 'Spring'
  and student_number is not null
```

`load_students` runs 2 queries against
`teamster-332318.kipptaf_powerschool.base_powerschool__student_enrollments`:
distinct `(student_number, state_studentnumber)` over all years for
`by_state_id`, and the rows with
`academic_year in (@school_year - 1, @school_year)` for `Student`. `current` is
the row with `academic_year = @school_year`, `rn_year = 1`, `enroll_status = 0`.
`last_spring_school` is the `school_name` of the row with
`academic_year = @school_year - 1`, `rn_year = 1`. Names and `dob` come from the
latest row. The dry run in Task 8 verifies these queries; they get no unit test.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/libraries/nj_isr/test_nj_isr_match.py -v` Expected:
PASS

- [ ] **Step 6: Commit**

```bash
git -C <worktree> add src/teamster/libraries/nj_isr tests/libraries/nj_isr
git -C <worktree> commit -m "feat(nj_isr): match records to students and route by current school"
```

---

### Task 4: Output files, index rows, and Sheet values

**Files:**

- Create: `src/teamster/libraries/nj_isr/layout.py`
- Test: `tests/libraries/nj_isr/test_nj_isr_layout.py`

**Interfaces:**

- Consumes: `Record`, `SourceFile`, `IsrFormatError` (Task 2); `Placement`,
  `TRANSFER_FOLDER` (Task 3).
- Produces:

```python
@dataclass(frozen=True)
class Entry:
    placement: Placement
    page_in_file: int        # first page of this record in the output file

@dataclass(frozen=True)
class OutputFile:
    region: str
    schoolid: int | None     # None means the region's transfer folder
    file_name: str
    entries: tuple[Entry, ...]
    @property
    def page_count(self) -> int: ...

@dataclass(frozen=True)
class IndexRow:
    student: str             # "Last, First"
    student_number: str      # "" when unmatched
    grade: str
    subject: str             # "ELA" | "Math" | "Science" | "See report"
    where: str
    last_spring_school: str
    file_name: str
    page: int
    note: str

def admin_label(source: SourceFile) -> str          # "Spring 2026"
def tag_value(source: SourceFile) -> str            # "2026_Spring_NJSLA"
def report_label(source: SourceFile) -> str
def year_folder_name(program: str, admin: str) -> str
def index_sheet_name(region: str, program: str, admin: str) -> str
def shortcut_name(program: str, admin: str) -> str
def build_output_files(placements: Sequence[Placement]) -> list[OutputFile]
def check_conservation(records_in: Sequence[Record], replaced: Sequence[Record],
                       files: Sequence[OutputFile]) -> None
def index_rows(files: Sequence[OutputFile]) -> dict[str, list[IndexRow]]
def sheet_tabs(rows: Sequence[IndexRow], links: Mapping[str, str], *, region: str,
               program: str, admin: str, ran_at: datetime,
               page_anchor: bool) -> dict[str, list[list[str]]]
```

- [ ] **Step 1: Write the failing tests**

```python
def test_names():
    assert report_label(src(variant="Combined")) == "NJSLA Reports"
    assert report_label(src(variant="Single")) == "NJSLA Science Reports"
    assert report_label(src(program="NJGPA", variant="")) == "NJGPA Reports"
    assert year_folder_name("NJSLA", "Spring 2026") == "Spring 2026 NJSLA ISRs"
    assert index_sheet_name("Newark", "NJSLA", "Spring 2026") == "Newark NJSLA Reports Index - Spring 2026"
    assert shortcut_name("NJSLA", "Spring 2026") == "00 - Find a student's NJSLA report - Spring 2026"

def test_build_output_files_groups_sorts_and_numbers_pages():
    files = build_output_files([at_team("Zane", "Ava", 3), at_team("Adams", "Bo", 1),
                                at_team("Adams", "Al", 2), unmatched_newark("ZED")])
    team = next(f for f in files if f.schoolid == 133570965)
    assert team.file_name == "KIPP TEAM Academy - NJSLA Reports - Spring 2026.pdf"
    assert [e.placement.resolution.student.first_name for e in team.entries] == ["Al", "Bo", "Ava"]
    assert [e.page_in_file for e in team.entries] == [1, 5, 9]
    transfer = next(f for f in files if f.schoolid is None)
    assert transfer.file_name == "Newark Transfer Out & Unmatched - NJSLA Reports - Spring 2026.pdf"

def test_unmatched_sort_after_matched_in_transfer_file():
    files = build_output_files([unmatched_newark("AARON ABLE"), left_newark("Zane", "Ava")])
    t = files[0]
    assert t.entries[0].placement.resolution.student is not None

def test_check_conservation_flags_a_lost_record():
    a, b = rec(seq=1), rec(seq=2)
    files = build_output_files([at_team_for(a)])
    with pytest.raises(IsrFormatError, match="conservation"):
        check_conservation([a, b], [], files)

def test_index_rows_one_per_subject_and_see_report():
    rows = index_rows(build_output_files([at_team("Adams", "Al", 1, subjects=("ELA", "Math")),
                                          at_team("Baker", "Bo", 2, subjects=())]))["Newark"]
    assert [(r.student, r.subject, r.page) for r in rows] == [
        ("Adams, Al", "ELA", 1), ("Adams, Al", "Math", 1), ("Baker, Bo", "See report", 5)]

def test_index_row_notes():
    row = index_rows(build_output_files([at_team("Adams", "Al", 1, reissue=date(2026, 10, 2))]))["Newark"][0]
    assert row.note == "Corrected by the state on 10/2"
    row = index_rows(build_output_files([unmatched_newark("AARON ABLE")]))["Newark"][0]
    assert (row.student, row.student_number, row.note) == ("Able, Aaron", "", "Not matched to a KTAF student")

def test_cross_region_row_goes_to_destination_region():
    rows = index_rows(build_output_files([at_paterson_from_newark("Adams", "Al")]))
    assert "Paterson" in rows and "Newark" not in rows

def test_index_never_shows_dob_state_id_or_code():
    tabs = sheet_tabs(index_rows(build_output_files([at_team("Adams", "Al", 1)]))["Newark"],
                      {}, region="Newark", program="NJSLA", admin="Spring 2026",
                      ran_at=datetime(2026, 10, 20, 9, 0), page_anchor=False)
    cells = [c for tab in tabs.values() for row in tab for c in row]
    assert not any(s in c for c in cells for s in ("1000000001", "03/04/15", "2015-03-04", "a1b2c3"))

def test_sheet_tabs_banner_header_and_link():
    tabs = sheet_tabs(rows_one_team(), {"KIPP TEAM Academy - NJSLA Reports - Spring 2026.pdf": "https://x/view"},
                      region="Newark", program="NJSLA", admin="Spring 2026",
                      ran_at=datetime(2026, 10, 20, 9, 0), page_anchor=True)
    a = tabs["All reports"]
    assert a[0] == ["Newark NJSLA reports - Spring 2026"]
    assert a[1] == ["1. Press Ctrl+F (Cmd+F on a Mac) and type the student's last name."]
    assert a[2] == ["2. Click the blue link in that student's row."]
    assert a[3] == ["3. Go to the page number in the Page column."]
    assert a[4] == ["Student", "Student number", "Grade when tested", "Subject",
                    "Where to find it", "School last spring", "Open the report", "Page", "Note"]
    assert a[5][6] == '=HYPERLINK("https://x/view#page=1", "Open report")'
    assert tabs["About"][1] == ["Last updated", "2026-10-20 09:00"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/libraries/nj_isr/test_nj_isr_layout.py -v` Expected:
FAIL with `ModuleNotFoundError` for `teamster.libraries.nj_isr.layout`

- [ ] **Step 3: Implement `layout.py`**

Group placements by `(region, schoolid, report_label)`. Sort entries by
matched-first, then `last_name.casefold()`, `first_name.casefold()`,
`student_number`. Unmatched records take their name from `printed_name`: the
last token is the last name, the rest is the first name, both `.title()`d.
`check_conservation` compares the multiset of `(source.path, seq)` across files
with `records_in` minus `replaced`, and raises
`IsrFormatError("conservation: ...")` on any difference. Notes join with `"; "`:

- correction: `Corrected by the state on {month}/{day}`
- not tested: `Not tested in at least 1 subject - see report`
- `no_candidate`: `Not matched to a KTAF student`
- `failed_confirmation` or `source_conflict`: `Needs a check by the Data team`

`About` tab rows, exactly:

```python
[["What this is", f"Every {admin} {program} Individual Student Report for {region}, one row per student per subject."],
 ["Last updated", ran_at.strftime("%Y-%m-%d %H:%M")],
 ["Can't find a report?", "Submit a ticket to the Data team."],
 ["Students who left KTAF", "Their reports are in the Transfer Out & Unmatched folder next to this Sheet."]]
```

Rows sort by `student`, then `subject`. Without a link, the link cell is `""`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/libraries/nj_isr/test_nj_isr_layout.py -v` Expected:
PASS

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add src/teamster/libraries/nj_isr/layout.py tests/libraries/nj_isr/test_nj_isr_layout.py
git -C <worktree> commit -m "feat(nj_isr): lay out school files and the regional index"
```

---

### Task 5: PDF read and write

**Files:**

- Create: `src/teamster/libraries/nj_isr/pdf_io.py`
- Test: `tests/libraries/nj_isr/test_nj_isr_pdf_io.py`

**Interfaces:**

- Consumes: `OutputFile` (Task 4).
- Produces:
  - `read_page_texts(path: Path) -> list[str]` (`pypdfium2`)
  - `write_output_pdf(file: OutputFile, out_dir: Path) -> Path` (`pypdf`; opens
    each source once, adds pages in entry order, runs
    `compress_identical_objects()`, writes `out_dir / file.file_name`)

- [ ] **Step 1: Write the failing test**

Build 2 source PDFs in `tmp_path` with `pypdf.PdfWriter.add_blank_page`, each
page a distinct width, so the output's page order is readable without text.

```python
def test_write_output_pdf_keeps_entry_order(tmp_path):
    a = blank_pdf(tmp_path / "a.pdf", widths=[100, 101, 102, 103])
    b = blank_pdf(tmp_path / "b.pdf", widths=[200, 201])
    f = output_file(entries=[entry(a, 3, 4), entry(b, 1, 2)])
    out = write_output_pdf(f, tmp_path)
    assert [int(p.mediabox.width) for p in PdfReader(out).pages] == [102, 103, 200, 201]
    assert out.name == f.file_name
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/libraries/nj_isr/test_nj_isr_pdf_io.py -v` Expected:
FAIL with `ModuleNotFoundError` for `teamster.libraries.nj_isr.pdf_io`

- [ ] **Step 3: Implement `pdf_io.py`**

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/libraries/nj_isr/test_nj_isr_pdf_io.py -v` Expected:
PASS

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add src/teamster/libraries/nj_isr/pdf_io.py tests/libraries/nj_isr/test_nj_isr_pdf_io.py
git -C <worktree> commit -m "feat(nj_isr): read page text and write school PDFs"
```

---

### Task 6: Drive and Sheets client

**Files:**

- Create: `src/teamster/libraries/nj_isr/drive.py`
- Test: `tests/libraries/nj_isr/test_nj_isr_drive.py`

**Interfaces:**

- Consumes: `MissingFolderError` (Task 2).
- Produces:

```python
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
FOLDER_MIME = "application/vnd.google-apps.folder"
SHEET_MIME = "application/vnd.google-apps.spreadsheet"
SHORTCUT_MIME = "application/vnd.google-apps.shortcut"
PDF_MIME = "application/pdf"

@dataclass(frozen=True)
class DriveFile:
    id: str
    name: str
    web_view_link: str

class DriveApi(Protocol):
    def find_child(self, parent_id: str, name: str, mime_type: str) -> DriveFile | None: ...
    def create(self, parent_id: str, name: str, mime_type: str, *,
               media_path: Path | None = None,
               app_properties: Mapping[str, str] | None = None,
               shortcut_target: str | None = None) -> DriveFile: ...
    def update_media(self, file_id: str, media_path: Path) -> DriveFile: ...
    def list_tagged(self, parent_id: str, key: str, value: str) -> list[DriveFile]: ...
    def trash(self, file_id: str) -> None: ...
    def readers(self, file_id: str) -> list[str]: ...
    def write_sheet(self, spreadsheet_id: str, tabs: Mapping[str, list[list[str]]]) -> None: ...

class GoogleDriveApi:  # implements DriveApi
    def __init__(self, credentials: google.auth.credentials.Credentials) -> None: ...

def escape_query_value(value: str) -> str
def folder_id_from_url(url_or_id: str) -> str
def load_user_credentials(gcloud_config_dir: Path) -> google.auth.credentials.Credentials
```

- [ ] **Step 1: Write the failing tests**

Mock the discovery services: set `api._drive = MagicMock()` and
`api._sheets = MagicMock()` after constructing with a dummy credential, the same
way `tests/resources/test_resource_google_directory.py` mocks its service.

```python
def test_escape_query_value():
    assert escape_query_value("O'Brien Report Cards") == "O\\'Brien Report Cards"
    assert escape_query_value("a\\b") == "a\\\\b"

def test_find_child_builds_query_and_passes_all_drives():
    api.find_child("parent123", "O'Brien Report Cards", FOLDER_MIME)
    kwargs = api._drive.files.return_value.list.call_args.kwargs
    assert "'parent123' in parents" in kwargs["q"]
    assert "name = 'O\\'Brien Report Cards'" in kwargs["q"]
    assert "trashed = false" in kwargs["q"]
    assert kwargs["supportsAllDrives"] is True and kwargs["includeItemsFromAllDrives"] is True

def test_find_child_raises_on_two_matches():
    list_returns([{"id": "a", "name": "X", "webViewLink": ""}, {"id": "b", "name": "X", "webViewLink": ""}])
    with pytest.raises(MissingFolderError, match="2 items named"):
        api.find_child("p", "X", FOLDER_MIME)

def test_create_sends_parents_tag_and_shortcut():
    api.create("p", "00 - Find", SHORTCUT_MIME, shortcut_target="sheet1")
    body = api._drive.files.return_value.create.call_args.kwargs["body"]
    assert body["parents"] == ["p"] and body["shortcutDetails"] == {"targetId": "sheet1"}

def test_update_media_targets_the_same_id(tmp_path):
    api.update_media("file1", write(tmp_path / "x.pdf"))
    assert api._drive.files.return_value.update.call_args.kwargs["fileId"] == "file1"

def test_folder_id_from_url():
    assert folder_id_from_url("https://drive.google.com/drive/folders/abc123?resourcekey=0-k") == "abc123"
    assert folder_id_from_url("abc123") == "abc123"

def test_load_user_credentials_explains_missing_sign_in(tmp_path):
    with pytest.raises(FileNotFoundError, match="gcloud auth application-default login"):
        load_user_credentials(tmp_path)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/libraries/nj_isr/test_nj_isr_drive.py -v` Expected:
FAIL with `ModuleNotFoundError` for `teamster.libraries.nj_isr.drive`

- [ ] **Step 3: Implement `drive.py`**

`GoogleDriveApi` builds `drive` v3 and `sheets` v4 with
`googleapiclient.discovery.build`. Every `files()` call passes
`supportsAllDrives=True`; `list` also passes `includeItemsFromAllDrives=True`
and requests `fields="files(id,name,webViewLink)"`. `list_tagged` queries
`appProperties has { key='{key}' and value='{value}' }`. `create` uploads with
`MediaFileUpload(media_path, mimetype=PDF_MIME, resumable=True)` when
`media_path` is set. `readers` lists permissions and returns each one as
`"{role}: {emailAddress or domain or type}"`. `write_sheet` adds any missing
tab, clears each tab, writes values with `valueInputOption="USER_ENTERED"`, and
on `All reports` freezes 5 rows, sets rows 1 to 4 to font size 14, and bolds
rows 1 and 5. `load_user_credentials` reads
`application_default_credentials.json` from the directory with
`google.auth.load_credentials_from_file(..., scopes=[DRIVE_SCOPE])`. When the
file is missing, raise `FileNotFoundError` whose message carries the Task 1
sign-in command.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/libraries/nj_isr/test_nj_isr_drive.py -v` Expected:
PASS

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add src/teamster/libraries/nj_isr/drive.py tests/libraries/nj_isr/test_nj_isr_drive.py
git -C <worktree> commit -m "feat(nj_isr): add a Drive and Sheets client that runs as the user"
```

---

### Task 7: Publish to Drive

**Files:**

- Create: `src/teamster/libraries/nj_isr/publish.py`
- Test: `tests/libraries/nj_isr/test_nj_isr_publish.py`

**Interfaces:**

- Consumes: `DriveApi`, `DriveFile`, the MIME constants (Task 6); `OutputFile`,
  `IndexRow`, `sheet_tabs`, `year_folder_name`, `index_sheet_name`,
  `shortcut_name` (Task 4); `REGION_FOLDERS`, `SCHOOL_FOLDERS` (Task 3);
  `TRANSFER_FOLDER` (Task 3); `MissingFolderError` (Task 2).
- Produces:

```python
TAG_KEY = "nj_isr_admin"

@dataclass(frozen=True)
class PublishResult:
    links: dict[str, str]          # file_name -> webViewLink
    sheets: dict[str, str]         # region -> Sheet webViewLink
    trashed: list[str]             # file names moved to the trash
    readers: dict[str, list[str]]  # region -> who can open the region's yearly folder

def publish(api: DriveApi, root_id: str, files: Sequence[OutputFile],
            pdf_paths: Mapping[str, Path], rows_by_region: Mapping[str, list[IndexRow]],
            *, program: str, admin: str, tag: str, ran_at: datetime,
            create_missing: bool, page_anchor: bool) -> PublishResult
```

- [ ] **Step 1: Write the failing tests**

Write `FakeDrive`, an in-memory `DriveApi` in the test file: a dict of items
with `id`, `name`, `mime_type`, `parent`, `app_properties`, `trashed`, and a
counter for new IDs. Record every create and update call so a test can assert
that nothing was written.

```python
def test_first_publish_builds_the_layout():
    drive = fake_drive_with_existing("Newark Report Cards and Transcripts", "TEAM Report Cards")
    result = publish(drive, "root", [team_file, newark_transfer_file], pdfs, rows, **KW)
    assert drive.path_exists("Newark Report Cards and Transcripts/Spring 2026 NJSLA ISRs/Newark NJSLA Reports Index - Spring 2026")
    assert drive.path_exists("Newark Report Cards and Transcripts/Spring 2026 NJSLA ISRs/Transfer Out & Unmatched/Newark Transfer Out & Unmatched - NJSLA Reports - Spring 2026.pdf")
    assert drive.path_exists("Newark Report Cards and Transcripts/TEAM Report Cards/Spring 2026 NJSLA ISRs/KIPP TEAM Academy - NJSLA Reports - Spring 2026.pdf")
    assert drive.path_exists("Newark Report Cards and Transcripts/TEAM Report Cards/Spring 2026 NJSLA ISRs/00 - Find a student's NJSLA report - Spring 2026")
    assert drive.tag_of("KIPP TEAM Academy - NJSLA Reports - Spring 2026.pdf") == {"nj_isr_admin": "2026_Spring_NJSLA"}
    assert drive.sheet_values("Newark NJSLA Reports Index - Spring 2026")["All reports"][5][0] == "Adams, Al"

def test_rerun_keeps_every_file_id():
    drive = fake_drive_with_existing(...)
    publish(drive, "root", files, pdfs, rows, **KW)
    before = drive.ids_by_path()
    publish(drive, "root", files, pdfs, rows, **KW)
    assert drive.ids_by_path() == before

def test_rerun_trashes_a_file_no_longer_produced():
    publish(drive, "root", [team_file, team_science_file], pdfs, rows, **KW)
    result = publish(drive, "root", [team_file], pdfs, rows, **KW)
    assert result.trashed == ["KIPP TEAM Academy - NJSLA Science Reports - Spring 2026.pdf"]

def test_missing_school_folder_stops_before_any_write():
    drive = fake_drive_with_existing("Newark Report Cards and Transcripts")  # no TEAM folder
    with pytest.raises(MissingFolderError, match="TEAM Report Cards"):
        publish(drive, "root", [team_file], pdfs, rows, **KW)
    assert drive.writes == []

def test_duplicate_school_folder_name_stops_before_any_write():
    drive = fake_drive_with_existing("Newark Report Cards and Transcripts", "TEAM Report Cards", "TEAM Report Cards")
    with pytest.raises(MissingFolderError):
        publish(drive, "root", [team_file], pdfs, rows, **KW)
    assert drive.writes == []

def test_create_missing_builds_folders_for_a_test_run():
    drive = fake_drive_with_existing()
    publish(drive, "root", [team_file], pdfs, rows, **{**KW, "create_missing": True})
    assert drive.path_exists("Newark Report Cards and Transcripts/TEAM Report Cards")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/libraries/nj_isr/test_nj_isr_publish.py -v` Expected:
FAIL with `ModuleNotFoundError` for `teamster.libraries.nj_isr.publish`

- [ ] **Step 3: Implement `publish.py`**

Order matters, because a failed lookup must leave Drive untouched:

1. Resolve every region folder and every school folder the files need, with
   `find_child` only. Collect every missing or doubled name and raise one
   `MissingFolderError` that lists them all, unless `create_missing` is set.
2. Per region: find or create the yearly folder, `Transfer Out & Unmatched`, and
   the index Sheet (created with the tag).
3. Upload each PDF: a tagged file with the same name in the target folder gets
   `update_media`, otherwise `create` with the tag.
4. Find or create the shortcut to the region's Sheet in each school yearly
   folder that received a file, and in `Transfer Out & Unmatched`.
5. Trash orphans: in the transfer folder and in every yearly folder under the
   region's configured school folders, trash each tagged file that this run did
   not produce.
6. Write the Sheet with `sheet_tabs(..., links=result.links)`.
7. Fill `readers` from the region's yearly folder.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/libraries/nj_isr/test_nj_isr_publish.py -v` Expected:
PASS

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add src/teamster/libraries/nj_isr/publish.py tests/libraries/nj_isr/test_nj_isr_publish.py
git -C <worktree> commit -m "feat(nj_isr): publish school files, transfer folders, and index to Drive"
```

---

### Task 8: Command line, summary, and dry run on the 2026 files

**Files:**

- Create: `src/teamster/libraries/nj_isr/run.py`
- Create: `src/teamster/libraries/nj_isr/__main__.py`
- Test: `tests/libraries/nj_isr/test_nj_isr_run.py`

**Interfaces:**

- Consumes: everything above.
- Produces, in `run.py`:

```python
@dataclass(frozen=True)
class RunPlan:
    program: str
    admin: str
    tag: str
    school_year: int
    records_in: list[Record]
    replaced: list[Record]
    unpaired_corrections: list[Record]
    duplicates: list[Record]
    placements: list[Placement]
    files: list[OutputFile]
    rows_by_region: dict[str, list[IndexRow]]

def build_plan(input_dir: Path, *, read_pages: Callable[[Path], list[str]],
               crosswalk: Mapping[str, set[int]], by_state_id: Mapping[str, set[int]],
               students: Mapping[int, Student], school_year: int | None = None) -> RunPlan
def summarize(plan: RunPlan, result: PublishResult | None) -> str
```

- `__main__.py` arguments: `--input DIR` (required), `--root-folder LINK`
  (required unless `--dry-run`), `--school-year INT` (default: the
  administration year), `--dry-run`, `--local-out DIR`,
  `--create-missing-folders`, `--page-anchor`, `--gcloud-config DIR` (default
  `~/.config/teamster/nj-isr-gcloud`).

- [ ] **Step 1: Write the failing tests**

```python
def test_build_plan_counts(tmp_path):
    touch(tmp_path, "2026_Spring_7325-965_ISR_SLA_Combined.pdf")
    touch(tmp_path, "2026_Spring_7325-965_ISR_SLA_Combined_100226.pdf")
    touch(tmp_path, "2026_Spring_7325-965_Labels_SLA.pdf")
    plan = build_plan(tmp_path, read_pages=fake_pages, crosswalk=XW, by_state_id={}, students=STUDENTS)
    assert (plan.program, plan.admin, plan.tag, plan.school_year) == ("NJSLA", "Spring 2026", "2026_Spring_NJSLA", 2026)
    assert len(plan.records_in) == 3 and len(plan.replaced) == 1
    assert sum(len(f.entries) for f in plan.files) == 2

def test_build_plan_stops_on_mixed_programs(tmp_path):
    touch(tmp_path, "2026_Spring_7325-965_ISR_SLA_Combined.pdf")
    touch(tmp_path, "2026_Spring_7325-965_ISR_GPA.pdf")
    with pytest.raises(IsrFormatError, match="program"):
        build_plan(tmp_path, read_pages=fake_pages, crosswalk={}, by_state_id={}, students={})

def test_build_plan_stops_when_a_school_has_no_folder_name(tmp_path):
    touch(tmp_path, "2026_Spring_7325-965_ISR_SLA_Combined.pdf")
    students = {101: replace(ALEX, current=Enrollment("Newark", 999, "New School"))}
    with pytest.raises(MissingFolderError, match="New School"):
        build_plan(tmp_path, read_pages=fake_pages, crosswalk=XW, by_state_id={}, students=students)

def test_summary_lists_counts_by_region_and_destination():
    text = summarize(small_plan(), None)
    assert "Newark  KIPP TEAM Academy  1 records" in text
    assert "Newark  Transfer Out & Unmatched  1 records" in text
    assert "Corrections applied: 1" in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/libraries/nj_isr/test_nj_isr_run.py -v` Expected: FAIL
with `ModuleNotFoundError` for `teamster.libraries.nj_isr.run`

- [ ] **Step 3: Implement `run.py` and `__main__.py`**

`build_plan` runs: `scan_folder`, `apply_corrections`,
`find_duplicate_state_ids`, `resolve` and `place` per record (testing region
from `REGION_BY_DISTRICT`), `build_output_files`, `check_conservation`,
`index_rows`. Before returning, it raises `MissingFolderError` naming every
current school whose `(region, schoolid)` is missing from `SCHOOL_FOLDERS`, so a
dry run catches a new school. `summarize` prints, in this order: counts per
`(region, where)`; corrections applied and unpaired corrections; duplicate state
IDs; each unmatched record (file, `seq`, printed name, reason); and, when
`result` is set, trashed files, each region's Sheet link, and its readers. The
summary is for the terminal only.

`__main__.py` loads the warehouse data, builds the plan, and prints the summary.
With `--dry-run` it writes PDFs only when `--local-out` is given, then stops.
Otherwise it writes PDFs to `--local-out` or a temporary folder, loads
credentials from `--gcloud-config`, calls `publish`, and prints the summary
again with the result.

- [ ] **Step 4: Run all of the library's tests**

Run: `uv run pytest tests/libraries/nj_isr -v` Expected: PASS

- [ ] **Step 5: Dry run on the real 2026 files**

Run:
`uv run python -m teamster.libraries.nj_isr --input "/workspaces/teamster/.claude/scratch/njsla-njgpa-isr/Spring 2026 ISRs" --dry-run --local-out <scratchpad>/nj_isr_out 2>&1 | tail -n 60`
Expected:

- no `IsrFormatError`, so record conservation passed
- 5,781 records across all destinations
- about 4,750 to 19 schools, about 1,025 to transfer folders, and a few dozen or
  fewer unmatched once the name and birth date check runs
- `KIPP TEAM Academy - NJSLA Reports - Spring 2026.pdf` near 9 MB in
  `<scratchpad>/nj_isr_out`

Read the unmatched list in the terminal. If the name and birth date check sends
more than 50 records to Unmatched, stop and show the user the reasons by count
before going on. The local PDFs hold student data: keep them in the scratchpad
and delete them after Task 9.

- [ ] **Step 6: Lint and commit**

Run:
`cd <worktree> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/teamster/libraries/nj_isr tests/libraries/nj_isr </dev/null 2>&1 | tail -n 20`
Expected: no lint issues. Then:

```bash
git -C <worktree> add src/teamster/libraries/nj_isr tests/libraries/nj_isr
git -C <worktree> commit -m "feat(nj_isr): add the yearly command and run summary"
```

---

### Task 9: Real run into the user's test folder

This task writes real student reports to the user's own test folder, so it needs
the user at each check.

- [ ] **Step 1: Run into the test folder**

Run:
`uv run python -m teamster.libraries.nj_isr --input "<isr folder>" --root-folder "<test folder link from Task 1>" --create-missing-folders --local-out <scratchpad>/nj_isr_out 2>&1 | tail -n 60`
Expected: the same counts as the Task 8 dry run, 3 Sheet links, and the user's
account as the only reader.

- [ ] **Step 2: Ask the user to check 3 things in Drive**

1. `KIPP TEAM Academy - NJSLA Reports - Spring 2026.pdf` previews in the browser
   without a download.
2. In the Newark index, 3 rows the user picks open the right file, and the page
   column lands on the right student.
3. The user pastes one link with `#page=` and the number from that row appended,
   and reports whether the viewer jumps to that page.

If item 1 fails, stop: the layout switches to one file per grade, which needs a
design change the user approves first.

- [ ] **Step 3: Rerun and compare file IDs**

Run the Step 1 command again. Expected: the summary's file links are identical
to the first run, and nothing is trashed.

- [ ] **Step 4: Turn on page links if they work**

If item 3 worked, make `--page-anchor` the default (`default=True` with a
`--no-page-anchor` flag), rerun `uv run pytest tests/libraries/nj_isr -v`, and
commit:

```bash
git -C <worktree> add src/teamster/libraries/nj_isr/__main__.py
git -C <worktree> commit -m "feat(nj_isr): link index rows straight to the student's page"
```

- [ ] **Step 5: Clean up**

Ask the user to delete the test folder from Drive. Delete
`<scratchpad>/nj_isr_out`.

---

### Task 10: Yearly runbook and pull request

**Files:**

- Create: `.claude/skills/nj-isr-reports/SKILL.md`

- [ ] **Step 1: Load the skill-writing rules**

Invoke `Skill` with `writing-for-agents` before writing the skill.

- [ ] **Step 2: Write the skill**

Trigger: the state releases NJSLA or NJGPA ISRs, a school cannot find an ISR, or
someone asks to rerun the split. Content, in order:

1. Download the ISR PDFs from the Cambium portal into
   `.claude/scratch/njsla-njgpa-isr/{season} {year} ISRs/`. Never commit them.
2. Update `SCHOOL_FOLDERS` in `destinations.py` for new or renamed schools.
3. Sign in (the Task 1 command).
4. Dry run, read the summary, resolve the unmatched list.
5. Test-folder run and the 3 checks from Task 9.
6. Real run, then confirm each region's readers in the summary.
7. Tell schools where the index lives.
8. Reruns: when corrections arrive or enrollment changes; links survive.

Name #6027: once the folders move to the Data Team shared drive, the command can
write as the service account instead.

- [ ] **Step 3: Lint and commit**

Run:
`cd <worktree> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/nj-isr-reports/SKILL.md </dev/null 2>&1 | tail -n 20`
Expected: no lint issues.

```bash
git -C <worktree> add .claude/skills/nj-isr-reports/SKILL.md
git -C <worktree> commit -m "docs(nj_isr): add the yearly runbook skill"
```

- [ ] **Step 4: Push and open the PR**

Push the branch and open the PR from `.github/pull_request_template.md`, with
`Closes #6026` and `Refs #6027`. The PR body names no student and no folder ID.
Then offer to watch CI and handle the `claude-review` findings, per
`pr-ci-review`.

---

### Task 11: Real run into school folders

Only after the user says to run it. This step puts reports in front of school
staff.

- [ ] **Step 1: Confirm the setup with the user**

The user confirms: the Paterson school folders exist with the names in
`SCHOOL_FOLDERS` and their school-level sharing; the account running the command
can edit every school folder.

- [ ] **Step 2: Run**

Run:
`uv run python -m teamster.libraries.nj_isr --input "<isr folder>" --root-folder "<Report Cards and Transcripts link>" 2>&1 | tail -n 80`
Expected: the Task 8 counts, 3 Sheet links, nothing trashed on the first run.

- [ ] **Step 3: Hand the sharing step to the user**

Show the user each region's readers from the summary. The user shares each
region's `Spring 2026 NJSLA ISRs` folder with that region's school staff, then
spot-checks the index with a school-level account.
