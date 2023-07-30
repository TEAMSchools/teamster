from teamster.core.utils.functions import get_avro_record_schema

GENDER_FIELDS = [
    {"name": "addressMeAs", "type": ["null", "string"], "default": None},
    {"name": "customGender", "type": ["null", "string"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
]

EMAIL_FIELDS = [
    {"name": "address", "type": ["null", "string"], "default": None},
    {"name": "customType", "type": ["null", "string"], "default": None},
    {"name": "primary", "type": ["null", "boolean"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
]

EXTERNAL_ID_FIELDS = [
    {"name": "customType", "type": ["null", "string"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
    {"name": "value", "type": ["null", "string"], "default": None},
]

RELATION_FIELDS = [
    {"name": "customType", "type": ["null", "string"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
    {"name": "value", "type": ["null", "string"], "default": None},
]

ADDRESS_FIELDS = [
    {"name": "country", "type": ["null", "string"], "default": None},
    {"name": "countryCode", "type": ["null", "string"], "default": None},
    {"name": "customType", "type": ["null", "string"], "default": None},
    {"name": "extendedAddress", "type": ["null", "string"], "default": None},
    {"name": "formatted", "type": ["null", "string"], "default": None},
    {"name": "locality", "type": ["null", "string"], "default": None},
    {"name": "poBox", "type": ["null", "string"], "default": None},
    {"name": "postalCode", "type": ["null", "string"], "default": None},
    {"name": "primary", "type": ["null", "boolean"], "default": None},
    {"name": "region", "type": ["null", "string"], "default": None},
    {"name": "sourceIsStructured", "type": ["null", "boolean"], "default": None},
    {"name": "streetAddress", "type": ["null", "string"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
]

ORGANIZATION_FIELDS = [
    {"name": "costCenter", "type": ["null", "string"], "default": None},
    {"name": "customType", "type": ["null", "string"], "default": None},
    {"name": "department", "type": ["null", "string"], "default": None},
    {"name": "description", "type": ["null", "string"], "default": None},
    {"name": "domain", "type": ["null", "string"], "default": None},
    {"name": "fullTimeEquivalent", "type": ["null", "long"], "default": None},
    {"name": "location", "type": ["null", "string"], "default": None},
    {"name": "name", "type": ["null", "string"], "default": None},
    {"name": "primary", "type": ["null", "boolean"], "default": None},
    {"name": "symbol", "type": ["null", "string"], "default": None},
    {"name": "title", "type": ["null", "string"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
]

PHONE_FIELDS = [
    {"name": "customType", "type": ["null", "string"], "default": None},
    {"name": "primary", "type": ["null", "boolean"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
    {"name": "value", "type": ["null", "string"], "default": None},
]

LANGUAGE_FIELDS = [
    {"name": "customLanguage", "type": ["null", "string"], "default": None},
    {"name": "languageCode", "type": ["null", "string"], "default": None},
    {"name": "preference", "type": ["null", "string"], "default": None},
]

POSIX_ACCOUNT_FIELDS = [
    {"name": "accountId", "type": ["null", "string"], "default": None},
    {"name": "gecos", "type": ["null", "string"], "default": None},
    {"name": "gid", "type": ["null", "long"], "default": None},
    {"name": "homeDirectory", "type": ["null", "string"], "default": None},
    {"name": "operatingSystemType", "type": ["null", "string"], "default": None},
    {"name": "primary", "type": ["null", "boolean"], "default": None},
    {"name": "shell", "type": ["null", "string"], "default": None},
    {"name": "systemId", "type": ["null", "string"], "default": None},
    {"name": "uid", "type": ["null", "long"], "default": None},
    {"name": "username", "type": ["null", "string"], "default": None},
]

SSH_PUBLIC_KEY_FIELDS = [
    {"name": "expirationTimeUsec", "type": ["null", "long"], "default": None},
    {"name": "fingerprint", "type": ["null", "string"], "default": None},
    {"name": "key", "type": ["null", "string"], "default": None},
]

NOTE_FIELDS = [
    {"name": "value", "type": ["null", "string"], "default": None},
    {"name": "contentType", "type": ["null", "string"], "default": None},
]

WEBSITE_FIELDS = [
    {"name": "customType", "type": ["null", "string"], "default": None},
    {"name": "primary", "type": ["null", "boolean"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
    {"name": "value", "type": ["null", "string"], "default": None},
]

LOCATION_FIELDS = [
    {"name": "area", "type": ["null", "string"], "default": None},
    {"name": "buildingId", "type": ["null", "string"], "default": None},
    {"name": "customType", "type": ["null", "string"], "default": None},
    {"name": "deskCode", "type": ["null", "string"], "default": None},
    {"name": "floorName", "type": ["null", "string"], "default": None},
    {"name": "floorSection", "type": ["null", "string"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
]

KEYWORD_FIELDS = [
    {"name": "customType", "type": ["null", "string"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
    {"name": "value", "type": ["null", "string"], "default": None},
]

IM_FIELDS = [
    {"name": "customProtocol", "type": ["null", "string"], "default": None},
    {"name": "customType", "type": ["null", "string"], "default": None},
    {"name": "im", "type": ["null", "string"], "default": None},
    {"name": "primary", "type": ["null", "boolean"], "default": None},
    {"name": "protocol", "type": ["null", "string"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
]

STUDENT_ATTRIBUTE_FIELDS = [
    {"name": "Student_Number", "type": ["null", "long"], "default": None},
]

CUSTOM_SCHEMA_FIELDS = [
    {
        "name": "Student_attributes",
        "type": [
            "null",
            get_avro_record_schema(
                name="student_attribute",
                fields=STUDENT_ATTRIBUTE_FIELDS,
                namespace="user.custom_schema",
            ),
        ],
        "default": None,
    },
]

PASSWORD_FIELDS = []

NAME_FIELDS = [
    {"name": "fullName", "type": ["null", "string"], "default": None},
    {"name": "familyName", "type": ["null", "string"], "default": None},
    {"name": "givenName", "type": ["null", "string"], "default": None},
    {"name": "displayName", "type": ["null", "string"], "default": None},
]

USER_FIELDS = [
    {"name": "agreedToTerms", "type": ["null", "boolean"], "default": None},
    {"name": "archived", "type": ["null", "boolean"], "default": None},
    {"name": "changePasswordAtNextLogin", "type": ["null", "boolean"], "default": None},
    {"name": "creationTime", "type": ["null", "string"], "default": None},
    {"name": "customerId", "type": ["null", "string"], "default": None},
    {"name": "deletionTime", "type": ["null", "string"], "default": None},
    {"name": "etag", "type": ["null", "string"], "default": None},
    {"name": "hashFunction", "type": ["null", "string"], "default": None},
    {"name": "id", "type": ["null", "string"], "default": None},
    {
        "name": "includeInGlobalAddressList",
        "type": ["null", "boolean"],
        "default": None,
    },
    {"name": "ipWhitelisted", "type": ["null", "boolean"], "default": None},
    {"name": "isAdmin", "type": ["null", "boolean"], "default": None},
    {"name": "isDelegatedAdmin", "type": ["null", "boolean"], "default": None},
    {"name": "isEnforcedIn2Sv", "type": ["null", "boolean"], "default": None},
    {"name": "isEnrolledIn2Sv", "type": ["null", "boolean"], "default": None},
    {"name": "isMailboxSetup", "type": ["null", "boolean"], "default": None},
    {"name": "kind", "type": ["null", "string"], "default": None},
    {"name": "lastLoginTime", "type": ["null", "string"], "default": None},
    {"name": "orgUnitPath", "type": ["null", "string"], "default": None},
    {"name": "primaryEmail", "type": ["null", "string"], "default": None},
    {"name": "recoveryEmail", "type": ["null", "string"], "default": None},
    {"name": "recoveryPhone", "type": ["null", "string"], "default": None},
    {"name": "suspended", "type": ["null", "boolean"], "default": None},
    {"name": "suspensionReason", "type": ["null", "string"], "default": None},
    {"name": "thumbnailPhotoEtag", "type": ["null", "string"], "default": None},
    {"name": "thumbnailPhotoUrl", "type": ["null", "string"], "default": None},
    {
        "name": "aliases",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "nonEditableAliases",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "name",
        "type": [
            "null",
            get_avro_record_schema(name="name", fields=NAME_FIELDS, namespace="user"),
        ],
        "default": None,
    },
    {
        "name": "gender",
        "type": [
            "null",
            get_avro_record_schema(
                name="gender", fields=GENDER_FIELDS, namespace="user"
            ),
        ],
        "default": None,
    },
    {
        "name": "password",
        "type": [
            "null",
            get_avro_record_schema(
                name="password", fields=PASSWORD_FIELDS, namespace="user"
            ),
        ],
        "default": None,
    },
    {
        "name": "addresses",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="addresses", fields=ADDRESS_FIELDS, namespace="user"
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "customSchemas",
        "type": [
            "null",
            get_avro_record_schema(
                name="custom_schemas", fields=CUSTOM_SCHEMA_FIELDS, namespace="user"
            ),
        ],
        "default": None,
    },
    {
        "name": "emails",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="emails", fields=EMAIL_FIELDS, namespace="user"
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "externalIds",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="external_ids", fields=EXTERNAL_ID_FIELDS, namespace="user"
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "ims",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="ims", fields=IM_FIELDS, namespace="user"
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "keywords",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="keywords", fields=KEYWORD_FIELDS, namespace="user"
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "languages",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="languages", fields=LANGUAGE_FIELDS, namespace="user"
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "locations",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="locations", fields=LOCATION_FIELDS, namespace="user"
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "notes",
        "type": [
            "null",
            get_avro_record_schema(name="notes", fields=NOTE_FIELDS, namespace="user")
            # {
            #     "type": "array",
            #     "items": get_avro_record_schema(
            #         name="notes", fields=NOTE_FIELDS, namespace="user"
            #     ),
            #     "default": [],
            # },
        ],
        "default": None,
    },
    {
        "name": "organizations",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="organizations", fields=ORGANIZATION_FIELDS, namespace="user"
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "phones",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="phones", fields=PHONE_FIELDS, namespace="user"
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "posixAccounts",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="posix_accounts", fields=POSIX_ACCOUNT_FIELDS, namespace="user"
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "relations",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="relations", fields=RELATION_FIELDS, namespace="user"
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "sshPublicKeys",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="ssh_public_keys",
                    fields=SSH_PUBLIC_KEY_FIELDS,
                    namespace="user",
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "websites",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="websites", fields=WEBSITE_FIELDS, namespace="user"
                ),
                "default": [],
            },
        ],
        "default": None,
    },
]

GROUP_FIELDS = [
    {"name": "id", "type": ["null", "string"], "default": None},
    {"name": "email", "type": ["null", "string"], "default": None},
    {"name": "name", "type": ["null", "string"], "default": None},
    {"name": "description", "type": ["null", "string"], "default": None},
    {"name": "adminCreated", "type": ["null", "boolean"], "default": None},
    {"name": "directMembersCount", "type": ["null", "string"], "default": None},
    {"name": "kind", "type": ["null", "string"], "default": None},
    {"name": "etag", "type": ["null", "string"], "default": None},
    {
        "name": "aliases",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
    {
        "name": "nonEditableAliases",
        "type": ["null", {"type": "array", "items": "string", "default": []}],
        "default": None,
    },
]

MEMBER_FIELDS = [
    {"name": "kind", "type": ["null", "string"], "default": None},
    {"name": "email", "type": ["null", "string"], "default": None},
    {"name": "role", "type": ["null", "string"], "default": None},
    {"name": "etag", "type": ["null", "string"], "default": None},
    {"name": "type", "type": ["null", "string"], "default": None},
    {"name": "status", "type": ["null", "string"], "default": None},
    {"name": "delivery_settings", "type": ["null", "string"], "default": None},
    {"name": "id", "type": ["null", "string"], "default": None},
]

ROLE_PRIVILEGE_FIELDS = [
    {"name": "serviceId", "type": ["null", "string"], "default": None},
    {"name": "privilegeName", "type": ["null", "string"], "default": None},
]

ROLE_FIELDS = [
    {"name": "roleId", "type": ["null", "string"], "default": None},
    {"name": "roleName", "type": ["null", "string"], "default": None},
    {"name": "roleDescription", "type": ["null", "string"], "default": None},
    {"name": "isSystemRole", "type": ["null", "boolean"], "default": None},
    {"name": "isSuperAdminRole", "type": ["null", "boolean"], "default": None},
    {"name": "kind", "type": ["null", "string"], "default": None},
    {"name": "etag", "type": ["null", "string"], "default": None},
    {
        "name": "rolePrivileges",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="role_privileges",
                    fields=ROLE_PRIVILEGE_FIELDS,
                    namespace="role",
                ),
                "default": [],
            },
        ],
        "default": None,
    },
]

ROLE_ASSIGNMENT_FIELDS = [
    {"name": "roleAssignmentId", "type": ["null", "string"], "default": None},
    {"name": "roleId", "type": ["null", "string"], "default": None},
    {"name": "kind", "type": ["null", "string"], "default": None},
    {"name": "etag", "type": ["null", "string"], "default": None},
    {"name": "assignedTo", "type": ["null", "string"], "default": None},
    {"name": "assigneeType", "type": ["null", "string"], "default": None},
    {"name": "scopeType", "type": ["null", "string"], "default": None},
    {"name": "orgUnitId", "type": ["null", "string"], "default": None},
    {"name": "condition", "type": ["null", "string"], "default": None},
]

ASSET_FIELDS = {
    "users": USER_FIELDS,
    "groups": GROUP_FIELDS,
    "members": MEMBER_FIELDS,
    "roles": ROLE_FIELDS,
    "role_assignments": ROLE_ASSIGNMENT_FIELDS,
}
