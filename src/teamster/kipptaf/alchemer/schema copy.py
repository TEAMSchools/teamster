from pydantic import BaseModel, Field


class Atom(BaseModel):
    type: str | None = None

    value: str | list[str | None] | None = None


class ShowRule(BaseModel):
    id: str | None = None
    operator: str | None = None

    same_page_skus: list[str | None] | None = None


class SurveyOptionProperty(BaseModel):
    all: bool | None = None
    checked: bool | None = None
    dependent: str | None = None
    disabled: bool | None = None
    fixed: bool | None = None
    na: bool | None = None
    none: bool | None = None
    other: bool | None = None
    otherrequired: bool | None = None
    requireother: bool | None = None
    piping_exclude: str | None = None
    show_rules_logic_map: str | None = None

    # field_left_label: dict[str, str | None] | None = Field(
    #     default=None, alias="left-label"
    # )
    # field_right_label: dict[str, str | None] | None = Field(
    #     default=None, alias="right-label"
    # )


class SurveyOption(BaseModel):
    id: int | None = None
    value: str | None = None

    title: dict[str, str | int | None] | None = None


class SurveyQuestionProperty(BaseModel):
    break_after: bool | None = None
    custom_css: str | None = None
    data_json: bool | None = None
    data_type: str | None = None
    disabled: bool | None = None
    element_style: str | None = None
    exclude_number: str | None = None
    extentions: str | None = None
    force_currency: bool | None = None
    force_int: bool | None = None
    force_numeric: bool | None = None
    force_percent: bool | None = None
    hidden: bool | None = None
    hide_after_response: bool | None = None
    labels_right: bool | None = None
    map_key: str | None = None
    max_number: str | None = None
    maxfiles: str | None = None
    min_answers_per_row: str | None = None
    min_number: str | None = None
    minimum_response: int | None = None
    only_whole_num: bool | None = None
    option_sort: str | None = None
    orientation: str | None = None
    question_description_above: bool | None = None
    required: bool | None = None
    show_title: bool | None = None
    sizelimit: int | None = None
    soft_required: bool | None = None
    sub_questions: int | None = None
    subtype: str | None = None
    url: str | None = None

    limits: list[str | None] | None = None

    defaulttext: dict[str, str | None] | None = None
    inputmask: dict[str, str | None] | None = None
    message: dict[str, str | None] | None = None
    question_description: dict[str, str | None] | None = None

    outbound: list[dict[str, str | None]] | None = None

    placeholder: list[str | None] | dict[str, str | None] | None = None

    messages: dict[str, list[str | None] | dict[str, str | None] | None] | None = None


class SurveyPageProperty(BaseModel):
    hidden: bool | None = None
    piped_from: str | None = None

    field_page_group: str | None = Field(default=None, alias="page-group")


class TeamItem(BaseModel):
    id: str | None = None
    name: str | None = None


class Action(BaseModel):
    complete: bool | None = None
    disqualify: bool | None = None
    jump: str | None = None
    redirect: bool | None = None
    save_data: bool | None = None


class SurveyDataAnswer(BaseModel):
    id: int | None = None
    option: str | None = None
    rank: str | None = None


class SurveyDataOptions(BaseModel):
    answer: str | None = None
    id: int | None = None
    option: str | None = None
    original_answer: str | None = None


"""
def get_atom_fields(namespace, depth=1):
    if depth > 0:
        return [
            {
                "name": "atom",
                "type": [
                    "null",
                    get_avro_record_schema(
                        name="atom",
                        fields=[
                            *ATOM_FIELDS,
                            *SHOW_RULE_FIELDS,
                            *get_atom_fields(
                                namespace=f"{namespace}.atom", depth=(depth - 1)
                            ),
                        ],
                        namespace=namespace,
                    ),
                ],
                "default": None,
            },
            {
                "name": "atom2",
                "type": [
                    "null",
                    get_avro_record_schema(
                        name="atom2",
                        fields=[
                            *ATOM_FIELDS,
                            *SHOW_RULE_FIELDS,
                            *get_atom_fields(
                                namespace=f"{namespace}.atom2", depth=(depth - 1)
                            ),
                        ],
                        namespace=namespace,
                    ),
                ],
                "default": None,
            }
        ]
    else:
        return []
"""


class Logic(ShowRule, Atom): ...


class Rule(BaseModel):
    logic_map: str | None = None

    actions: Action | None = None
    logic: Logic | None = None


"""
def get_survey_question_property_fields(namespace):
    return [
        *SURVEY_QUESTION_PROPERTY_FIELDS,
        {

            "name": "show_rules",
            "type": [
                "null",
                get_avro_record_schema(
                    name="show_rule",
                    fields=[
                        *SHOW_RULE_FIELDS,
                        *ATOM_FIELDS,
                        *get_atom_fields(namespace=f"{namespace}.show_rule", depth=1),
                    ],
                    namespace=namespace,
                ),
            ],
            "default": None,
        },
        {
            "name": "rules",
            "type": [
                "null",
                get_avro_record_schema(
                    name="rule",
                    fields=get_rule_fields(namespace=f"{namespace}.rule"),
                    namespace=namespace,
                ),
            ],
            "default": None,
        }
    ]


def get_survey_option_property_fields(namespace):
    return [
        *SURVEY_OPTION_PROPERTY_FIELDS,
        {
            "name": "show_rules",
            "type": [
                "null",
                get_avro_record_schema(
                    name="show_rule",
                    fields=[
                        *SHOW_RULE_FIELDS,
                        *ATOM_FIELDS,
                        *get_atom_fields(namespace=f"{namespace}.show_rule", depth=1),
                    ],
                    namespace=namespace,
                ),
            ],
            "default": None,
        }
    ]


def get_survey_option_fields(namespace):
    return [
        *SURVEY_OPTION_FIELDS,
        {
            "name": "properties",
            "type": [
                "null",
                get_avro_record_schema(
                    name="property",
                    fields=get_survey_option_property_fields(
                        namespace=f"{namespace}.property"
                    ),
                    namespace=namespace,
                ),
            ],
            "default": None,
        }
    ]


def get_survey_question_fields(namespace, depth=1):
    if depth > 0:
        return [
            *SURVEY_QUESTION_FIELDS,
            {
                "name": "properties",
                "type": [
                    "null",
                    get_avro_record_schema(
                        name="property",
                        fields=get_survey_question_property_fields(
                            namespace=f"{namespace}.property"
                        ),
                        namespace=namespace,
                    ),
                ],
                "default": None,
            }
            {
                "name": "options",
                "type": [
                    "null",
                    {
                        "type": "array",
                        "items": get_avro_record_schema(
                            name="option",
                            fields=get_survey_option_fields(
                                namespace=f"{namespace}.option"
                            ),
                            namespace=namespace,
                        ),
                        "default": [],
                    }
                ],
                "default": None,
            }
            {
                "name": "sub_questions",
                "type": [
                    "null",
                    {
                        "type": "array",
                        "items": get_avro_record_schema(
                            name="question",
                            fields=get_survey_question_fields(
                                namespace=f"{namespace}.sub_question",
                                depth=(depth - 1),
                            ),
                            namespace=namespace,
                        ),
                        "default": [],
                    }
                ],
                "default": None,
            }
        ]
    else:
        return []
"""


class SurveyPage(BaseModel):
    field_id: int | None = Field(default=None, alias="id")

    title: list[str | None] | dict[str, str | None] | None = None
    description: list[str | None] | dict[str, str | None] | None = None

    properties: list[str | None] | SurveyPageProperty | None = None
    questions: list[SurveyQuestion | None] | None = None


class SurveyData(BaseModel):
    parent: int | None = None
    question: str | None = None
    section_id: int | None = None
    original_answer: str | None = None
    shown: bool | None = None

    field_id: int | None = Field(default=None, alias="id")
    field_type: int | None = Field(default=None, alias="type")

    answer_id: int | str | None = None

    options: dict[str, SurveyDataOptions | None] | None = None

    answer: str | dict[str, str | SurveyDataAnswer | None] | None = None

    subquestions: dict[str, SurveyData | dict[str, SurveyData | None] | None] | None = (
        None
    )


class Statistics(BaseModel):
    Partial: int | None = None
    Disqualified: int | None = None
    Deleted: int | None = None
    Complete: int | None = None
    TestData: str | None = None


class Links(BaseModel):
    default: str | None = None
    campaign: str | None = None


class SurveyResponse(BaseModel):
    city: str | None = None
    comments: str | None = None
    contact_id: str | None = None
    country: str | None = None
    date_started: str | None = None
    date_submitted: str | None = None
    dma: str | None = None
    ip_address: str | None = None
    is_test_data: str | None = None
    language: str | None = None
    latitude: str | None = None
    link_id: str | None = None
    longitude: str | None = None
    postal: str | None = None
    referer: str | None = None
    region: str | None = None
    response_time: int | None = None
    session_id: str | None = None
    status: str | None = None
    user_agent: str | None = None

    field_id: str | None = Field(default=None, alias="id")

    url_variables: list[str | None] | dict[str, dict[str, str]] | None = None

    survey_data: list[str | None] | dict[str, SurveyData | None] | None = None

    data_quality: (
        list[str | None]
        | dict[str, int | list[str | None] | dict[str, int | list[str | None] | None]]
    )


class SurveyCampaign(BaseModel):
    close_message: str | None = None
    date_created: str | None = None
    date_modified: str | None = None
    id: str | None = None
    invite_id: str | None = None
    language: str | None = None
    limit_responses: str | None = None
    link_close_date: str | None = None
    link_open_date: str | None = None
    link_type: str | None = None
    name: str | None = None
    primary_theme_content: str | None = None
    primary_theme_options: str | None = None
    SSL: str | None = None
    status: str | None = None
    subtype: str | None = None
    token_variables: str | None = None
    type: str | None = None
    uri: str | None = None


class SurveyQuestion(BaseModel):
    base_type: str | None = None
    comment: bool | None = None
    description: list[str | None] | None = None
    has_showhide_deps: bool | None = None
    id: int | None = None
    options: list[Option | None] | None = None
    options: list[SurveyOption | None] | None = None
    properties: Properties | None = None
    properties: SurveyQuestionProperty | None = None
    shortname: str | None = None
    sub_questions: list[SurveyQuestion | None] | None = None
    title: dict[str, str | None] | None = None
    type: str | None = None
    varname: list[str | None] | dict[str, str | None] | None = None


class Survey(BaseModel):
    auto_close: str | None = None
    blockby: str | None = None
    created_on: str | None = None
    forward_only: bool | None = None
    id: str | None = None
    internal_title: str | None = None
    modified_on: str | None = None
    overall_quota: str | None = None
    status: str | None = None
    theme: str | None = None
    title: str | None = None
    type: str | None = None

    links: Links | None = None
    statistics: Statistics | None = None

    languages: list[str | None] | None = None

    title_ml: dict[str, str | None] | None = None

    team: list[TeamItem | None] | None = None
