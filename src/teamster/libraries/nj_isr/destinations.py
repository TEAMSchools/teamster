REGION_BY_DISTRICT: dict[str, str] = {
    "7325": "Newark",
    "1799": "Camden",
    "7899": "Paterson",
}

# Districts that must each have an original ISR file before a run publishes.
# Paterson (7899) joins NJGPA once it has a grade 11.
PROGRAM_DISTRICTS: dict[str, tuple[str, ...]] = {
    "NJSLA": ("7325", "1799", "7899"),
    "NJGPA": ("7325", "1799"),
}

REGION_FOLDERS: dict[str, str] = {
    "Newark": "Newark Report Cards and Transcripts",
    "Camden": "Camden Report Cards and Transcripts",
    "Paterson": "Paterson Report Cards and Transcripts",
}

# (region, PowerSchool schoolid) -> school folder name
SCHOOL_FOLDERS: dict[tuple[str, int], str] = {
    ("Newark", 73258): "BOLD Report Cards",
    ("Newark", 732513): "Justice Report Cards",
    ("Newark", 73257): "Life Report Cards",
    ("Newark", 73253): "NCA Report Cards",
    ("Newark", 732511): "Lab Report Cards",
    ("Newark", 732514): "Purpose Report Cards",
    ("Newark", 73252): "Rise Report Cards",
    ("Newark", 73254): "SPARK Report Cards",
    ("Newark", 73256): "Seek Report Cards",
    ("Newark", 133570965): "TEAM Report Cards",
    ("Newark", 73255): "THRIVE Report Cards",
    ("Newark", 73259): "KURA Report Cards",
    ("Camden", 179901): "LSP Report Cards",
    ("Camden", 179902): "LSM Report Cards",
    ("Camden", 179903): "Hatch Report Cards",
    ("Camden", 179904): "KHS Report Cards",
    ("Camden", 179905): "Sumner Report Cards",
    ("Paterson", 1234): "Paterson Prep Elementary Report Cards",
    ("Paterson", 2): "Paterson Prep Middle Report Cards",
}
