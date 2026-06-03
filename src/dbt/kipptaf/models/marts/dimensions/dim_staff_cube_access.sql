-- Dummy implementation: hardcoded data team members with full network-level
-- access. Replace with HR-derived logic per spec 2026-06-03-cube-security-redesign
-- once role-mapping rules are confirmed (#4102).
select
    staff_google_email,
    student_access_level,
    staff_access_level,
    student_pii,
    staff_pii,
    staff_compensation,
    staff_benefits,
    location_scope,
    cast(null as string) as location_scope_key,
from
    unnest(
        [
            struct(
                'cbaldor@apps.teamschools.org' as staff_google_email,
                'detail' as student_access_level,
                'detail' as staff_access_level,
                true as student_pii,
                true as staff_pii,
                true as staff_compensation,
                true as staff_benefits,
                'network' as location_scope
            ),
            struct(
                'ldesimon@apps.teamschools.org',
                'detail',
                'detail',
                true,
                true,
                true,
                true,
                'network'
            ),
            struct(
                'cbini@apps.teamschools.org',
                'detail',
                'detail',
                true,
                true,
                true,
                true,
                'network'
            ),
            struct(
                'kshaw@apps.teamschools.org',
                'detail',
                'detail',
                true,
                true,
                true,
                true,
                'network'
            ),
            struct(
                'kverhoff@apps.teamschools.org',
                'detail',
                'detail',
                true,
                true,
                true,
                true,
                'network'
            ),
            struct(
                'awalters@apps.teamschools.org',
                'detail',
                'detail',
                true,
                true,
                true,
                true,
                'network'
            ),
            struct(
                'skramer@apps.teamschools.org',
                'detail',
                'detail',
                true,
                true,
                true,
                true,
                'network'
            ),
            struct(
                'ssmall@apps.teamschools.org',
                'detail',
                'detail',
                true,
                true,
                true,
                true,
                'network'
            )
        ]
    )
