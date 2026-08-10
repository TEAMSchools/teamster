# KIPP TEAM and Family data platform

The shared vocabulary for the network's data models. Terms are added as they get
pinned down in design work, so this file grows in clusters rather than arriving
complete.

## Language

### KIPP Forward and postsecondary aid

**KIPP Forward**: The network's postsecondary program, supporting students from
middle school through college and career. Its legacy name survives inside
identifiers such as `ktc_status`.

_Avoid_: KTC, KIPP Through College

**Student**: A person holding a Salesforce contact record whose record type is
one of the student lifecycle stages. Parents, staff, and other contacts on the
same object are not students.

_Avoid_: alum, alumni, contact

**Salesforce contact ID**: The eighteen-character Salesforce identifier for a
contact record, and the network's canonical identifier for a student outside the
student information system. The SIS holds no identifier of its own for a
Salesforce record.

_Avoid_: SF ID, contact ID, `salesforce_id`

**KTC status**: Where a student sits relative to KIPP secondary enrollment —
enrolled at a given grade level, graduated from a KIPP high school, or a KIPP
middle school graduate who has not graduated from a KIPP high school.

_Avoid_: postsecondary status, record type, lifecycle stage

**Record type**: The lifecycle stage a Salesforce contact record was last set
to. It describes the state of the record, not the state of the student, and lags
real transitions in both directions.

_Avoid_: status, KTC status

**Maher Fund**: The fund from which the network pays discretionary awards to
KIPP Forward students, divided into emergency and enrichment purposes.

**Emergency funding request**: A request to pay Maher Fund money toward an
urgent, unplanned need of a single student.

_Avoid_: emergency aid, hardship grant, micro-grant

**Disbursement**: One payment of Maher Fund money made to or on behalf of one
student.

_Avoid_: award, grant, aid payment

**Cohort**: The year-group a student is associated with for KIPP high school
graduation.

_Avoid_: class, graduating class, grad year

**Region**: One of the four cities whose schools the network operates — Newark,
Camden, Miami, and Paterson.

_Avoid_: district, market, area
