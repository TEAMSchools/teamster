"""Check ps_programs.yaml against the live special programs view."""

from __future__ import annotations

from teamster.goal_setting.adapters import sql_list
from teamster.goal_setting.config import Crosswalk

SPENROLLMENTS = "`teamster-332318.kipptaf_powerschool.int_powerschool__spenrollments`"
REGION_TO_PROJECT = {
    "Camden": "kippcamden",
    "Newark": "kippnewark",
    "Paterson": "kipppaterson",
    "Miami": "kippmiami",
}
PROJECT_TO_REGION = {v: k for k, v in REGION_TO_PROJECT.items()}
DISCIPLINE = {"Reading": "ELA", "Math": "Math"}


def sql(regions: list[str]) -> str:
    projects = [REGION_TO_PROJECT[r] for r in regions]
    # trunk-ignore(bandit/B608): identifiers come from a validated mapping, not user input
    return f"""
    select
        regexp_extract(_dbt_source_relation, r'(kipp\\w+)_') as project,
        programid,
        specprog_name
    from {SPENROLLMENTS}
    where specprog_name like 'Bucket%'
      and regexp_extract(_dbt_source_relation, r'(kipp\\w+)_') in ({sql_list(projects)})
    group by project, programid, specprog_name
    """


def expected_name(subject: str, bucket: str) -> str:
    return f"{bucket} - {DISCIPLINE[subject]}"


def compare(xw: Crosswalk, live_rows: list[dict]) -> list[str]:
    problems = []
    live = {(r["region"], int(r["programid"])): r["specprog_name"] for r in live_rows}
    for p in xw.programs:
        name = live.get((p.region, p.programid))
        want = expected_name(p.subject, p.bucket)
        if name is None:
            problems.append(
                f"{p.region}: crosswalk program id {p.programid} ({want}) not found in PowerSchool"
            )
        elif name != want:
            problems.append(
                f"{p.region}: program id {p.programid} is '{name}' in PowerSchool but '{want}' in crosswalk"
            )
    known = {(p.region, p.programid) for p in xw.programs}
    for (region, pid), name in sorted(live.items()):
        if (region, pid) not in known:
            problems.append(
                f"{region}: PowerSchool bucket program {pid} '{name}' is not in crosswalk"
            )
    return problems


def run(client, xw: Crosswalk) -> list[str]:
    regions = sorted({p.region for p in xw.programs})
    rows = [
        {
            "region": PROJECT_TO_REGION[r["project"]],
            "programid": r["programid"],
            "specprog_name": r["specprog_name"],
        }
        for r in client.query(sql(regions)).result()
    ]
    return compare(xw, rows)
