from dataclasses import dataclass
from datetime import date
from pathlib import Path


class IsrFormatError(ValueError):
    """A state ISR file or its page text does not have the expected structure."""


class MissingFolderError(RuntimeError):
    """A Drive folder the run needs does not exist."""


@dataclass(frozen=True)
class SourceFile:
    """A state ISR PDF, described by its filename.

    Attributes:
        path: Location of the PDF.
        year: Administration year, for example 2026.
        season: Administration season, for example "Spring".
        district: State district code, for example "7325".
        school_code: State school code, for example "965".
        program: "NJSLA" or "NJGPA".
        variant: "Combined", "Single", or "" when the filename has none.
        reissue_date: Date from a trailing _MMDDYY, set only on a corrected
            report from the state.
    """

    path: Path
    year: int
    season: str
    district: str
    school_code: str
    program: str
    variant: str
    reissue_date: date | None


@dataclass(frozen=True)
class Record:
    """One student's pages in a state ISR PDF.

    Attributes:
        source: The file the pages come from.
        seq: Position of the record in the file, starting at 1.
        page_start: First page, 1-based and inclusive, in the source file.
        page_end: Last page, 1-based and inclusive, in the source file.
        state_id: The student's 10-digit state ID.
        printed_name: Name as printed on the report, "" if absent.
        printed_dob: Date of birth as printed, None if absent.
        grade: Enrolled grade as printed, None if absent.
        subjects: Ordered subset of ("ELA", "Math", "Science").
        not_tested: True when the report says the student was not tested.
    """

    source: SourceFile
    seq: int
    page_start: int
    page_end: int
    state_id: str
    printed_name: str
    printed_dob: date | None
    grade: int | None
    subjects: tuple[str, ...]
    not_tested: bool

    @property
    def page_count(self) -> int:
        return self.page_end - self.page_start + 1
