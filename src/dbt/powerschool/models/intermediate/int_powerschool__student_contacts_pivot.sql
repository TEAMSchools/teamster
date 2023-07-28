with
    people as (
        select
            studentid,
            student_number,
            personid,
            'contact' as person_type,
            relationship_type,
            concat(
                ltrim(rtrim(firstname)), ' ', ltrim(rtrim(lastname))
            ) as contact_name,
            contactpriorityorder,
        from {{ ref("int_powerschool__contacts") }}
        where person_type != 'self' and contactpriorityorder <= 2

        union all

        select
            studentid,
            student_number,
            personid,
            'emergency' as person_type,
            relationship_type,
            concat(
                ltrim(rtrim(firstname)), ' ', ltrim(rtrim(lastname))
            ) as contact_name,
            row_number() over (
                partition by studentid order by contactpriorityorder
            ) as contactpriorityorder,
        from {{ ref("int_powerschool__contacts") }}
        where person_type != 'self' and contactpriorityorder > 2 and isemergency = 1

        union all

        select
            studentid,
            student_number,
            personid,
            'pickup' as person_type,
            relationship_type,
            concat(
                ltrim(rtrim(firstname)), ' ', ltrim(rtrim(lastname))
            ) as contact_name,
            row_number() over (
                partition by studentid order by contactpriorityorder
            ) as contactpriorityorder,
        from {{ ref("int_powerschool__contacts") }}
        where
            person_type != 'self'
            and contactpriorityorder > 2
            and schoolpickupflg = 1
            and isemergency = 0
    ),

    person_contacts as (
        select
            c.studentid,
            c.student_number,
            concat(c.person_type, '_', c.contactpriorityorder) as person_type,

            lower(pc.contact_category)
            || '_'
            || lower(pc.contact_type) as contact_category_type,
            pc.contact,

            row_number() over (
                partition by
                    c.studentid, c.personid, pc.contact_category, pc.contact_type
                order by pc.priority_order
            ) as contact_category_type_priority,
        from people as c
        inner join
            {{ ref("int_powerschool__person_contacts") }} as pc
            on c.personid = pc.personid

        union all

        select
            c.studentid,
            c.student_number,
            concat(c.person_type, '_', c.contactpriorityorder) as person_type,

            'phone_primary' as contact_category_type,

            pc.contact,

            row_number() over (
                partition by c.studentid, c.personid
                order by pc.is_primary desc, pc.priority_order asc
            ) as contact_category_type_priority,
        from people as c
        inner join
            {{ ref("int_powerschool__person_contacts") }} as pc
            on c.personid = pc.personid
            and pc.contact_category = 'Phone'

        union all

        select
            studentid,
            student_number,
            concat(person_type, '_', contactpriorityorder) as person_type,
            'name' as contact_category_type,
            ltrim(rtrim(contact_name)) as contact,
            1 as contact_category_type_priority,
        from people

        union all

        select
            studentid,
            student_number,
            concat(person_type, '_', contactpriorityorder) as person_type,
            'relationship' as contact_category_type,
            relationship_type as contact,
            1 as contact_category_type_priority,
        from people
    ),

    pre_pivot as (
        select
            studentid,
            student_number,
            person_type || '_' || contact_category_type as pivot_column,
            contact as input_column,
        from person_contacts
        where contact_category_type_priority = 1
    )

select
    studentid,
    student_number,
    contact_1_address_home,
    contact_1_email_current,
    contact_1_name,
    contact_1_phone_daytime,
    contact_1_phone_home,
    contact_1_phone_mobile,
    contact_1_phone_primary,
    contact_1_phone_work,
    contact_1_relationship,
    contact_2_address_home,
    contact_2_email_current,
    contact_2_name,
    contact_2_phone_daytime,
    contact_2_phone_home,
    contact_2_phone_mobile,
    contact_2_phone_primary,
    contact_2_phone_work,
    contact_2_relationship,
    emergency_1_address_home,
    emergency_1_email_current,
    emergency_1_name,
    emergency_1_phone_daytime,
    emergency_1_phone_home,
    emergency_1_phone_mobile,
    emergency_1_phone_primary,
    emergency_1_phone_work,
    emergency_1_relationship,
    emergency_2_address_home,
    emergency_2_email_current,
    emergency_2_name,
    emergency_2_phone_daytime,
    emergency_2_phone_home,
    emergency_2_phone_mobile,
    emergency_2_phone_primary,
    emergency_2_phone_work,
    emergency_2_relationship,
    emergency_3_address_home,
    emergency_3_email_current,
    emergency_3_name,
    emergency_3_phone_daytime,
    emergency_3_phone_home,
    emergency_3_phone_mobile,
    emergency_3_phone_primary,
    emergency_3_phone_work,
    emergency_3_relationship,
    pickup_1_address_home,
    pickup_1_email_current,
    pickup_1_name,
    pickup_1_phone_daytime,
    pickup_1_phone_home,
    pickup_1_phone_mobile,
    pickup_1_phone_primary,
    pickup_1_phone_work,
    pickup_1_relationship,
    pickup_2_address_home,
    pickup_2_email_current,
    pickup_2_name,
    pickup_2_phone_daytime,
    pickup_2_phone_home,
    pickup_2_phone_mobile,
    pickup_2_phone_primary,
    pickup_2_phone_work,
    pickup_2_relationship,
    pickup_3_address_home,
    pickup_3_email_current,
    pickup_3_name,
    pickup_3_phone_daytime,
    pickup_3_phone_home,
    pickup_3_phone_mobile,
    pickup_3_phone_primary,
    pickup_3_phone_work,
    pickup_3_relationship,
from
    pre_pivot pivot (
        max(input_column) for pivot_column in (
            'contact_1_address_home',
            'contact_1_email_current',
            'contact_1_name',
            'contact_1_phone_daytime',
            'contact_1_phone_home',
            'contact_1_phone_mobile',
            'contact_1_phone_primary',
            'contact_1_phone_work',
            'contact_1_relationship',
            'contact_2_address_home',
            'contact_2_email_current',
            'contact_2_name',
            'contact_2_phone_daytime',
            'contact_2_phone_home',
            'contact_2_phone_mobile',
            'contact_2_phone_primary',
            'contact_2_phone_work',
            'contact_2_relationship',
            'emergency_1_address_home',
            'emergency_1_email_current',
            'emergency_1_name',
            'emergency_1_phone_daytime',
            'emergency_1_phone_home',
            'emergency_1_phone_mobile',
            'emergency_1_phone_primary',
            'emergency_1_phone_work',
            'emergency_1_relationship',
            'emergency_2_address_home',
            'emergency_2_email_current',
            'emergency_2_name',
            'emergency_2_phone_daytime',
            'emergency_2_phone_home',
            'emergency_2_phone_mobile',
            'emergency_2_phone_primary',
            'emergency_2_phone_work',
            'emergency_2_relationship',
            'emergency_3_address_home',
            'emergency_3_email_current',
            'emergency_3_name',
            'emergency_3_phone_daytime',
            'emergency_3_phone_home',
            'emergency_3_phone_mobile',
            'emergency_3_phone_primary',
            'emergency_3_phone_work',
            'emergency_3_relationship',
            'pickup_1_address_home',
            'pickup_1_email_current',
            'pickup_1_name',
            'pickup_1_phone_daytime',
            'pickup_1_phone_home',
            'pickup_1_phone_mobile',
            'pickup_1_phone_primary',
            'pickup_1_phone_work',
            'pickup_1_relationship',
            'pickup_2_address_home',
            'pickup_2_email_current',
            'pickup_2_name',
            'pickup_2_phone_daytime',
            'pickup_2_phone_home',
            'pickup_2_phone_mobile',
            'pickup_2_phone_primary',
            'pickup_2_phone_work',
            'pickup_2_relationship',
            'pickup_3_address_home',
            'pickup_3_email_current',
            'pickup_3_name',
            'pickup_3_phone_daytime',
            'pickup_3_phone_home',
            'pickup_3_phone_mobile',
            'pickup_3_phone_primary',
            'pickup_3_phone_work',
            'pickup_3_relationship',
            'pickup_4_address_home',
            'pickup_4_email_current',
            'pickup_4_name',
            'pickup_4_phone_daytime',
            'pickup_4_phone_home',
            'pickup_4_phone_mobile',
            'pickup_4_phone_primary',
            'pickup_4_phone_work',
            'pickup_4_relationship',
            'pickup_5_address_home',
            'pickup_5_email_current',
            'pickup_5_name',
            'pickup_5_phone_daytime',
            'pickup_5_phone_home',
            'pickup_5_phone_mobile',
            'pickup_5_phone_primary',
            'pickup_5_phone_work',
            'pickup_5_relationship'
        )
    )
