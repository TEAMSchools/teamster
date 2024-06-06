# trunk-ignore-all(pyright/reportIncompatibleVariableOverride)
import json

import py_avro_schema

from teamster.libraries.schoolmint.grow.schema import (
    Assignment,
    AssignmentPresetTag,
    Attachment,
    Checkbox,
    GenericTag,
    Informal,
    MagicNote,
    Measurement,
    Meeting,
    MeetingTypeTag,
    Observation,
    ObservationScore,
    Progress,
    Ref,
    Role,
    Rubric,
    School,
    Tag,
    TagNote,
    TagTag,
    TeachingAssignment,
    TextBox,
    User,
    UserRef,
    UserTypeTag,
    Video,
    VideoNote,
    VideoRef,
)


class creator_record(UserRef):
    """helper classes for backwards compatibility"""


class parent_record(Ref):
    """helper classes for backwards compatibility"""


class progress_record(Progress):
    """helper classes for backwards compatibility"""


class user_record(UserRef):
    """helper classes for backwards compatibility"""


class tag_record(Tag):
    """helper classes for backwards compatibility"""


class rubric_record(Ref):
    """helper classes for backwards compatibility"""


class observer_record(UserRef):
    """helper classes for backwards compatibility"""


class teacher_record(UserRef):
    """helper classes for backwards compatibility"""


class tag_note_1_record(TagNote):
    """helper classes for backwards compatibility"""


class tag_note_2_record(TagNote):
    """helper classes for backwards compatibility"""


class tag_note_3_record(TagNote):
    """helper classes for backwards compatibility"""


class tag_note_4_record(TagNote):
    """helper classes for backwards compatibility"""


class teaching_assignment_record(TeachingAssignment):
    """helper classes for backwards compatibility"""


class magic_note_record(MagicNote):
    """helper classes for backwards compatibility"""


class video_note_record(VideoNote):
    """helper classes for backwards compatibility"""


class attachment_record(Attachment):
    """helper classes for backwards compatibility"""


class video_record(VideoRef):
    """helper classes for backwards compatibility"""


class checkbox_record(Checkbox):
    """helper classes for backwards compatibility"""


class text_box_record(TextBox):
    """helper classes for backwards compatibility"""


class observation_score_record(ObservationScore):
    """helper classes for backwards compatibility"""

    checkboxes: list[checkbox_record | None] | None = None
    textBoxes: list[text_box_record | None] | None = None


class assignments_record(Assignment):
    """helper classes for backwards compatibility"""

    creator: creator_record | None = None
    parent: parent_record | None = None
    progress: progress_record | None = None
    user: user_record | None = None

    tags: list[tag_record | None] | None = None


class observations_record(Observation):
    """helper classes for backwards compatibility"""

    rubric: rubric_record | None = None
    observer: observer_record | None = None
    teacher: teacher_record | None = None
    tagNotes1: tag_note_1_record | None = None
    tagNotes2: tag_note_2_record | None = None
    tagNotes3: tag_note_3_record | None = None
    tagNotes4: tag_note_4_record | None = None
    teachingAssignment: teaching_assignment_record | None = None

    observationScores: list[observation_score_record | None] | None = None
    magicNotes: list[magic_note_record | None] | None = None
    videoNotes: list[video_note_record | None] | None = None
    attachments: list[attachment_record | None] | None = None
    videos: list[video_record | None] | None = None


# add namespace to assignment.parent for backwards compatibility
ASSIGNMENT_SCHEMA = json.loads(
    py_avro_schema.generate(
        py_type=assignments_record,
        options=py_avro_schema.Option.USE_FIELD_ALIAS
        | py_avro_schema.Option.NO_DOC
        | py_avro_schema.Option.NO_AUTO_NAMESPACE,
    )
)
assignment_parent = [f for f in ASSIGNMENT_SCHEMA["fields"] if f["name"] == "parent"][0]
assignment_parent["type"][1]["namespace"] = "assignment"

ASSET_SCHEMA = {
    "generic-tags/assignmentpresets": json.loads(
        py_avro_schema.generate(
            py_type=AssignmentPresetTag,
            namespace="assignmentpreset",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "generic-tags/courses": json.loads(
        py_avro_schema.generate(
            py_type=GenericTag,
            namespace="course",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "generic-tags/eventtag1": json.loads(
        py_avro_schema.generate(
            py_type=GenericTag,
            namespace="eventtag",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "generic-tags/goaltypes": json.loads(
        py_avro_schema.generate(
            py_type=GenericTag,
            namespace="goaltype",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "generic-tags/grades": json.loads(
        py_avro_schema.generate(
            py_type=GenericTag,
            namespace="grade",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "generic-tags/measurementgroups": json.loads(
        py_avro_schema.generate(
            py_type=GenericTag,
            namespace="measurementgroup",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "generic-tags/meetingtypes": json.loads(
        py_avro_schema.generate(
            py_type=MeetingTypeTag,
            namespace="meetingtype",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "generic-tags/observationtypes": json.loads(
        py_avro_schema.generate(
            py_type=GenericTag,
            namespace="observationtype",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "generic-tags/rubrictag1": json.loads(
        py_avro_schema.generate(
            py_type=GenericTag,
            namespace="rubrictag",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "generic-tags/schooltag1": json.loads(
        py_avro_schema.generate(
            py_type=GenericTag,
            namespace="schooltag",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "generic-tags/tags": json.loads(
        py_avro_schema.generate(
            py_type=TagTag,
            namespace="tag",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "generic-tags/usertag1": json.loads(
        py_avro_schema.generate(
            py_type=GenericTag,
            namespace="usertag",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "generic-tags/usertypes": json.loads(
        py_avro_schema.generate(
            py_type=UserTypeTag,
            namespace="usertype",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "informals": json.loads(
        py_avro_schema.generate(
            py_type=Informal,
            namespace="informal",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "measurements": json.loads(
        py_avro_schema.generate(
            py_type=Measurement,
            namespace="measurement",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "meetings": json.loads(
        py_avro_schema.generate(
            py_type=Meeting,
            namespace="meeting",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "roles": json.loads(
        py_avro_schema.generate(
            py_type=Role,
            namespace="role",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "rubrics": json.loads(
        py_avro_schema.generate(
            py_type=Rubric,
            namespace="rubric",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "schools": json.loads(
        py_avro_schema.generate(
            py_type=School,
            namespace="school",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "users": json.loads(
        py_avro_schema.generate(
            py_type=User,
            namespace="user",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "videos": json.loads(
        py_avro_schema.generate(
            py_type=Video,
            namespace="video",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "observations": json.loads(
        py_avro_schema.generate(
            py_type=observations_record,
            options=py_avro_schema.Option.USE_FIELD_ALIAS
            | py_avro_schema.Option.NO_DOC
            | py_avro_schema.Option.NO_AUTO_NAMESPACE,
        )
    ),
    "assignments": ASSIGNMENT_SCHEMA,
}
