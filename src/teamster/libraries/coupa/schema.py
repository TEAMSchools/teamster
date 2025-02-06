from pydantic import BaseModel, Field


class UserBase(BaseModel):
    id: int | None = None
    login: str | None = None
    email: str | None = None
    firstname: str | None = None
    lastname: str | None = None
    fullname: str | None = None
    employee_number: str | None = Field(None, alias="employee-number")
    salesforce_id: str | None = Field(None, alias="salesforce-id")
    avatar_thumb_url: str | None = Field(None, alias="avatar-thumb-url")


class ContentGroup(BaseModel):
    id: int | None = None
    name: str | None = None
    description: str | None = None
    created_at: str | None = Field(None, alias="created-at")
    updated_at: str | None = Field(None, alias="updated-at")

    created_by: UserBase | None = Field(None, alias="created-by")
    updated_by: UserBase | None = Field(None, alias="updated-by")


class Lookup(BaseModel):
    id: int | None = None
    active: bool | None = None
    name: str | None = None
    description: str | None = None
    created_at: str | None = Field(None, alias="created-at")
    updated_at: str | None = Field(None, alias="updated-at")
    fixed_depth: bool | None = Field(None, alias="fixed-depth")
    level_1_name: str | None = Field(None, alias="level-1-name")
    level_2_name: str | None = Field(None, alias="level-2-name")
    level_3_name: str | None = Field(None, alias="level-3-name")
    level_4_name: str | None = Field(None, alias="level-4-name")
    level_5_name: str | None = Field(None, alias="level-5-name")
    level_6_name: str | None = Field(None, alias="level-6-name")
    level_7_name: str | None = Field(None, alias="level-7-name")
    level_8_name: str | None = Field(None, alias="level-8-name")
    level_9_name: str | None = Field(None, alias="level-9-name")
    level_10_name: str | None = Field(None, alias="level-10-name")

    content_groups: list[ContentGroup] | None = Field(None, alias="content-groups")


class EntityCustomFields(BaseModel):
    ccc_entity: str | None = Field(None, alias="ccc-entity")
    ccc_entity_currency: str | None = Field(None, alias="ccc-entity-currency")
    ccc_tax_line: bool | None = Field(None, alias="ccc-tax-line")


class ExtensionField(BaseModel):
    id: int | None = None
    active: bool | None = None
    name: str | None = None
    description: str | None = None
    depth: int | None = None
    created_at: str | None = Field(None, alias="created-at")
    updated_at: str | None = Field(None, alias="updated-at")
    external_ref_num: str | None = Field(None, alias="external-ref-num")
    external_ref_code: str | None = Field(None, alias="external-ref-code")
    parent_id: str | None = Field(None, alias="parent-id")
    lookup_id: int | None = Field(None, alias="lookup-id")
    is_default: bool | None = Field(None, alias="is-default")

    lookup: Lookup | None = None
    custom_fields: EntityCustomFields | None = Field(None, alias="custom-fields")


class UserCustomFields(BaseModel):
    ccc_external_id: str | None = Field(None, alias="ccc-external-id")

    school_name: str | ExtensionField | None = Field(None, alias="school-name")
    sage_intacct_department: str | ExtensionField | None = Field(
        None, alias="sage-intacct-department"
    )
    sage_intacct_fund: str | ExtensionField | None = Field(
        None, alias="sage-intacct-fund"
    )
    sage_intacct_location: str | ExtensionField | None = Field(
        None, alias="sage-intacct-location"
    )
    sage_intacct_program: str | ExtensionField | None = Field(
        None, alias="sage-intacct-program"
    )


class Country(BaseModel):
    id: int | None = None
    code: str | None = None
    name: str | None = None


class TaxRegistration(BaseModel):
    id: int | None = None
    number: str | None = None
    active: bool | None = None
    local: bool | None = None
    owner_id: int | None = Field(None, alias="owner-id")
    owner_type: str | None = Field(None, alias="owner-type")

    country: Country | None = None
    created_at: UserBase | None = Field(None, alias="created-at")
    updated_at: UserBase | None = Field(None, alias="updated-at")


class VatCountry(BaseModel):
    id: int | None = None
    code: str | None = None
    name: str | None = None


class Address(BaseModel):
    id: int | None = None
    name: str | None = None
    street1: str | None = None
    street2: str | None = None
    street3: str | None = None
    street4: str | None = None
    city: str | None = None
    state: str | None = None
    attention: str | None = None
    active: bool | None = None
    type: str | None = None
    created_at: str | None = Field(None, alias="created-at")
    updated_at: str | None = Field(None, alias="updated-at")
    location_code: str | None = Field(None, alias="location-code")
    postal_code: str | None = Field(None, alias="postal-code")
    business_group_name: str | None = Field(None, alias="business-group-name")
    vat_number: str | None = Field(None, alias="vat-number")
    local_tax_number: str | None = Field(None, alias="local-tax-number")

    country: Country | None = None
    created_by: UserBase | None = Field(None, alias="created-by")
    updated_by: UserBase | None = Field(None, alias="updated-by")
    vat_country: VatCountry | None = Field(None, alias="vat-country")

    purposes: list[str] | None = None
    content_groups: list[ContentGroup] | None = Field(None, alias="content-groups")
    tax_registrations: list[TaxRegistration] | None = Field(
        None, alias="tax-registrations"
    )


class Currency(BaseModel):
    id: int | None = None
    code: str | None = None
    decimals: int | None = None


class AccountType(BaseModel):
    id: int | None = None
    name: str | None = None
    active: bool | None = None
    created_at: str | None = Field(None, alias="created-at")
    updated_at: str | None = Field(None, alias="updated-at")
    legal_entity_name: str | None = Field(None, alias="legal-entity-name")
    dynamic_flag: bool | None = Field(None, alias="dynamic-flag")

    currency: Currency | None = None
    primary_address: Address | None = Field(None, alias="primary-address")
    created_by: UserBase | None = Field(None, alias="created-by")
    updated_by: UserBase | None = Field(None, alias="updated-by")


class Account(BaseModel):
    id: int | None = None
    name: str | None = None
    code: str | None = None
    active: bool | None = None
    created_at: str | None = Field(None, alias="created-at")
    updated_at: str | None = Field(None, alias="updated-at")
    account_type_id: int | None = Field(None, alias="account-type-id")
    segment_1: str | None = Field(None, alias="segment-1")
    segment_2: str | None = Field(None, alias="segment-2")
    segment_3: str | None = Field(None, alias="segment-3")
    segment_4: str | None = Field(None, alias="segment-4")
    segment_5: str | None = Field(None, alias="segment-5")
    segment_6: str | None = Field(None, alias="segment-6")
    segment_7: str | None = Field(None, alias="segment-7")
    segment_8: str | None = Field(None, alias="segment-8")
    segment_9: str | None = Field(None, alias="segment-9")
    segment_10: str | None = Field(None, alias="segment-10")
    segment_11: str | None = Field(None, alias="segment-11")
    segment_12: str | None = Field(None, alias="segment-12")
    segment_13: str | None = Field(None, alias="segment-13")
    segment_14: str | None = Field(None, alias="segment-14")
    segment_15: str | None = Field(None, alias="segment-15")
    segment_16: str | None = Field(None, alias="segment-16")
    segment_17: str | None = Field(None, alias="segment-17")
    segment_18: str | None = Field(None, alias="segment-18")
    segment_19: str | None = Field(None, alias="segment-19")
    segment_20: str | None = Field(None, alias="segment-20")

    account_type: AccountType | None = Field(None, alias="account-type")


class AccountGroup(BaseModel):
    id: int | None = None
    name: str | None = None
    created_at: str | None = Field(None, alias="created-at")
    updated_at: str | None = Field(None, alias="updated-at")
    segment_1_col: str | None = Field(None, alias="segment-1-col")
    segment_1_op: str | None = Field(None, alias="segment-1-op")
    segment_1_val: str | None = Field(None, alias="segment-1-val")
    segment_2_col: str | None = Field(None, alias="segment-2-col")
    segment_2_op: str | None = Field(None, alias="segment-2-op")
    segment_2_val: str | None = Field(None, alias="segment-2-val")
    segment_3_col: str | None = Field(None, alias="segment-3-col")
    segment_3_op: str | None = Field(None, alias="segment-3-op")
    segment_3_val: str | None = Field(None, alias="segment-3-val")
    segment_4_col: str | None = Field(None, alias="segment-4-col")
    segment_4_op: str | None = Field(None, alias="segment-4-op")
    segment_4_val: str | None = Field(None, alias="segment-4-val")
    segment_5_col: str | None = Field(None, alias="segment-5-col")
    segment_5_op: str | None = Field(None, alias="segment-5-op")
    segment_5_val: str | None = Field(None, alias="segment-5-val")
    segment_6_col: str | None = Field(None, alias="segment-6-col")
    segment_6_op: str | None = Field(None, alias="segment-6-op")
    segment_6_val: str | None = Field(None, alias="segment-6-val")
    segment_7_col: str | None = Field(None, alias="segment-7-col")
    segment_7_op: str | None = Field(None, alias="segment-7-op")
    segment_7_val: str | None = Field(None, alias="segment-7-val")
    segment_8_col: str | None = Field(None, alias="segment-8-col")
    segment_8_op: str | None = Field(None, alias="segment-8-op")
    segment_8_val: str | None = Field(None, alias="segment-8-val")
    segment_9_col: str | None = Field(None, alias="segment-9-col")
    segment_9_op: str | None = Field(None, alias="segment-9-op")
    segment_9_val: str | None = Field(None, alias="segment-9-val")
    segment_10_col: str | None = Field(None, alias="segment-10-col")
    segment_10_op: str | None = Field(None, alias="segment-10-op")
    segment_10_val: str | None = Field(None, alias="segment-10-val")
    segment_11_col: str | None = Field(None, alias="segment-11-col")
    segment_11_op: str | None = Field(None, alias="segment-11-op")
    segment_11_val: str | None = Field(None, alias="segment-11-val")
    segment_12_col: str | None = Field(None, alias="segment-12-col")
    segment_12_op: str | None = Field(None, alias="segment-12-op")
    segment_12_val: str | None = Field(None, alias="segment-12-val")
    segment_13_col: str | None = Field(None, alias="segment-13-col")
    segment_13_op: str | None = Field(None, alias="segment-13-op")
    segment_13_val: str | None = Field(None, alias="segment-13-val")
    segment_14_col: str | None = Field(None, alias="segment-14-col")
    segment_14_op: str | None = Field(None, alias="segment-14-op")
    segment_14_val: str | None = Field(None, alias="segment-14-val")
    segment_15_col: str | None = Field(None, alias="segment-15-col")
    segment_15_op: str | None = Field(None, alias="segment-15-op")
    segment_15_val: str | None = Field(None, alias="segment-15-val")
    segment_16_col: str | None = Field(None, alias="segment-16-col")
    segment_16_op: str | None = Field(None, alias="segment-16-op")
    segment_16_val: str | None = Field(None, alias="segment-16-val")
    segment_17_col: str | None = Field(None, alias="segment-17-col")
    segment_17_op: str | None = Field(None, alias="segment-17-op")
    segment_17_val: str | None = Field(None, alias="segment-17-val")
    segment_18_col: str | None = Field(None, alias="segment-18-col")
    segment_18_op: str | None = Field(None, alias="segment-18-op")
    segment_18_val: str | None = Field(None, alias="segment-18-val")
    segment_19_col: str | None = Field(None, alias="segment-19-col")
    segment_19_op: str | None = Field(None, alias="segment-19-op")
    segment_19_val: str | None = Field(None, alias="segment-19-val")
    segment_20_col: str | None = Field(None, alias="segment-20-col")
    segment_20_op: str | None = Field(None, alias="segment-20-op")
    segment_20_val: str | None = Field(None, alias="segment-20-val")

    account_type: AccountType | None = Field(None, alias="account-type")
    created_by: UserBase | None = Field(None, alias="created-by")
    updated_by: UserBase | None = Field(None, alias="updated-by")


class BusinessGroup(BaseModel):
    id: int | None = None
    name: str | None = None
    description: str | None = None
    created_at: str | None = Field(None, alias="created-at")
    updated_at: str | None = Field(None, alias="updated-at")

    updated_by: UserBase | None = Field(None, alias="updated-by")
    created_by: UserBase | None = Field(None, alias="created-by")


class ApprovalLimit(BaseModel):
    id: int | None = None
    name: str | None = None
    amount: str | None = None
    subject: str | None = None
    created_at: str | None = Field(None, alias="created-at")
    updated_at: str | None = Field(None, alias="updated-at")

    currency: Currency | None = None
    created_by: UserBase | None = Field(None, alias="created-by")
    updated_by: UserBase | None = Field(None, alias="updated-by")


class Role(BaseModel):
    id: int | None = None
    name: str | None = None
    description: str | None = None
    omnipotent: bool | None = None
    created_at: str | None = Field(None, alias="created-at")
    updated_at: str | None = Field(None, alias="updated-at")
    system_role: bool | None = Field(None, alias="system-role")

    updated_by: UserBase | None = Field(None, alias="updated-by")
    created_by: UserBase | None = Field(None, alias="created-by")


class UserGroup(BaseModel):
    id: int | None = None
    type: str | None = None
    name: str | None = None
    active: bool | None = None
    open: bool | None = None
    description: str | None = None
    created_at: str | None = Field(None, alias="created-at")
    updated_at: str | None = Field(None, alias="updated-at")
    can_approve: bool | None = Field(None, alias="can-approve")
    mention_name: str | None = Field(None, alias="mention-name")
    avatar_thumb_url: str | None = Field(None, alias="avatar-thumb-url")

    updated_by: UserBase | None = Field(None, alias="updated-by")
    created_by: UserBase | None = Field(None, alias="created-by")

    users: list[UserBase] | None = None
    content_groups: list[ContentGroup] | None = Field(None, alias="content-groups")


class User(UserBase):
    id: int | None = None
    login: str | None = None
    email: str | None = None
    firstname: str | None = None
    lastname: str | None = None
    fullname: str | None = None
    employee_number: str | None = Field(None, alias="employee-number")
    salesforce_id: str | None = Field(None, alias="salesforce-id")
    avatar_thumb_url: str | None = Field(None, alias="avatar-thumb-url")
    middlename: str | None = None
    active: bool | None = None
    created_at: str | None = Field(None, alias="created-at")
    updated_at: str | None = Field(None, alias="updated-at")
    purchasing_user: bool | None = Field(None, alias="purchasing-user")
    expense_user: bool | None = Field(None, alias="expense-user")
    sourcing_user: bool | None = Field(None, alias="sourcing-user")
    inventory_user: bool | None = Field(None, alias="inventory-user")
    contracts_user: bool | None = Field(None, alias="contracts-user")
    analytics_user: bool | None = Field(None, alias="analytics-user")
    aic_user: bool | None = Field(None, alias="aic-user")
    spend_guard_user: bool | None = Field(None, alias="spend-guard-user")
    ccw_user: bool | None = Field(None, alias="ccw-user")
    clm_advanced_user: bool | None = Field(None, alias="clm-advanced-user")
    supply_chain_user: bool | None = Field(None, alias="supply-chain-user")
    risk_assess_user: bool | None = Field(None, alias="risk-assess-user")
    travel_user: bool | None = Field(None, alias="travel-user")
    treasury_user: bool | None = Field(None, alias="treasury-user")
    api_user: bool | None = Field(None, alias="api-user")
    account_security_type: int | None = Field(None, alias="account-security-type")
    authentication_method: str | None = Field(None, alias="authentication-method")
    sso_identifier: str | None = Field(None, alias="sso-identifier")
    default_locale: str | None = Field(None, alias="default-locale")
    business_group_security_type: int | None = Field(
        None, alias="business-group-security-type"
    )
    mention_name: str | None = Field(None, alias="mention-name")
    seniority_level: str | None = Field(None, alias="seniority-level")
    business_function: str | None = Field(None, alias="business-function")
    employee_payment_channel: str | None = Field(None, alias="employee-payment-channel")
    allow_employee_payment_account_creation: bool | None = Field(
        None, alias="allow-employee-payment-account-creation"
    )
    category_planner_user: bool | None = Field(None, alias="category-planner-user")

    custom_fields: UserCustomFields | None = Field(None, alias="custom-fields")
    default_account: Account | None = Field(None, alias="default-account")
    default_account_type: AccountType | None = Field(None, alias="default-account-type")
    default_address: Address | None = Field(None, alias="default-address")
    default_currency: Currency | None = Field(None, alias="default-currency")
    requisition_approval_limit: ApprovalLimit | None = Field(
        None, alias="requisition-approval-limit"
    )
    expense_approval_limit: ApprovalLimit | None = Field(
        None, alias="expense-approval-limit"
    )
    invoice_approval_limit: ApprovalLimit | None = Field(
        None, alias="invoice-approval-limit"
    )
    contract_approval_limit: ApprovalLimit | None = Field(
        None, alias="contract-approval-limit"
    )
    requisition_self_approval_limit: ApprovalLimit | None = Field(
        None, alias="requisition-self-approval-limit"
    )
    expense_self_approval_limit: ApprovalLimit | None = Field(
        None, alias="expense-self-approval-limit"
    )
    invoice_self_approval_limit: ApprovalLimit | None = Field(
        None, alias="invoice-self-approval-limit"
    )
    contract_self_approval_limit: ApprovalLimit | None = Field(
        None, alias="contract-self-approval-limit"
    )
    created_by: UserBase | None = Field(None, alias="created-by")
    updated_by: UserBase | None = Field(None, alias="updated-by")

    working_warehouses: list[str] | None = Field(None, alias="working-warehouses")
    inventory_organizations: list[str] | None = Field(
        None, alias="inventory-organizations"
    )

    roles: list[Role] | None = None
    expenses_delegated_to: list[UserBase] | None = Field(
        None, alias="expenses-delegated-to"
    )
    can_expense_for: list[UserBase] | None = Field(None, alias="can-expense-for")
    content_groups: list[ContentGroup] | None = Field(None, alias="content-groups")
    account_groups: list[AccountGroup] | None = Field(None, alias="account-groups")
    approval_groups: list[UserGroup] | None = Field(None, alias="approval-groups")
    user_groups: list[UserGroup] | None = Field(None, alias="user-groups")
