from pydantic import BaseModel


class UserBase(BaseModel):
    id: int | None = None
    login: str | None = None
    email: str | None = None
    firstname: str | None = None
    lastname: str | None = None
    fullname: str | None = None
    employee_number: str | None = None
    salesforce_id: str | None = None
    avatar_thumb_url: str | None = None


class ContentGroup(BaseModel):
    id: int | None = None
    name: str | None = None
    description: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    created_by: UserBase | None = None
    updated_by: UserBase | None = None


class Lookup(BaseModel):
    id: int | None = None
    active: bool | None = None
    name: str | None = None
    description: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    fixed_depth: bool | None = None
    level_1_name: str | None = None
    level_2_name: str | None = None
    level_3_name: str | None = None
    level_4_name: str | None = None
    level_5_name: str | None = None
    level_6_name: str | None = None
    level_7_name: str | None = None
    level_8_name: str | None = None
    level_9_name: str | None = None
    level_10_name: str | None = None

    content_groups: list[ContentGroup] | None = None


class EntityCustomFields(BaseModel):
    ccc_entity: str | None = None
    ccc_entity_currency: str | None = None
    ccc_tax_line: bool | None = None


class ExtensionField(BaseModel):
    id: int | None = None
    active: bool | None = None
    name: str | None = None
    description: str | None = None
    depth: int | None = None
    created_at: str | None = None
    updated_at: str | None = None
    external_ref_num: str | None = None
    external_ref_code: str | None = None
    parent_id: str | None = None
    lookup_id: int | None = None
    is_default: bool | None = None

    lookup: Lookup | None = None
    custom_fields: EntityCustomFields | None = None


class UserCustomFields(BaseModel):
    ccc_external_id: str | None = None

    school_name: str | ExtensionField | None = None
    sage_intacct_department: str | ExtensionField | None = None
    sage_intacct_fund: str | ExtensionField | None = None
    sage_intacct_location: str | ExtensionField | None = None
    sage_intacct_program: str | ExtensionField | None = None


class Country(BaseModel):
    id: int | None = None
    code: str | None = None
    name: str | None = None


class TaxRegistration(BaseModel):
    id: int | None = None
    number: str | None = None
    active: bool | None = None
    local: bool | None = None
    owner_id: int | None = None
    owner_type: str | None = None

    country: Country | None = None
    created_at: UserBase | None = None
    updated_at: UserBase | None = None


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
    created_at: str | None = None
    updated_at: str | None = None
    location_code: str | None = None
    postal_code: str | None = None
    business_group_name: str | None = None
    vat_number: str | None = None
    local_tax_number: str | None = None

    country: Country | None = None
    created_by: UserBase | None = None
    updated_by: UserBase | None = None
    vat_country: VatCountry | None = None

    purposes: list[str] | None = None
    content_groups: list[ContentGroup] | None = None
    tax_registrations: list[TaxRegistration] | None = None


class Currency(BaseModel):
    id: int | None = None
    code: str | None = None
    decimals: int | None = None


class AccountType(BaseModel):
    id: int | None = None
    name: str | None = None
    active: bool | None = None
    created_at: str | None = None
    updated_at: str | None = None
    legal_entity_name: str | None = None
    dynamic_flag: bool | None = None

    currency: Currency | None = None
    primary_address: Address | None = None
    created_by: UserBase | None = None
    updated_by: UserBase | None = None


class Account(BaseModel):
    id: int | None = None
    name: str | None = None
    code: str | None = None
    active: bool | None = None
    created_at: str | None = None
    updated_at: str | None = None
    account_type_id: int | None = None
    segment_1: str | None = None
    segment_2: str | None = None
    segment_3: str | None = None
    segment_4: str | None = None
    segment_5: str | None = None
    segment_6: str | None = None
    segment_7: str | None = None
    segment_8: str | None = None
    segment_9: str | None = None
    segment_10: str | None = None
    segment_11: str | None = None
    segment_12: str | None = None
    segment_13: str | None = None
    segment_14: str | None = None
    segment_15: str | None = None
    segment_16: str | None = None
    segment_17: str | None = None
    segment_18: str | None = None
    segment_19: str | None = None
    segment_20: str | None = None

    account_type: AccountType | None = None


class AccountGroup(BaseModel):
    id: int | None = None
    name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    segment_1_col: str | None = None
    segment_1_op: str | None = None
    segment_1_val: str | None = None
    segment_2_col: str | None = None
    segment_2_op: str | None = None
    segment_2_val: str | None = None
    segment_3_col: str | None = None
    segment_3_op: str | None = None
    segment_3_val: str | None = None
    segment_4_col: str | None = None
    segment_4_op: str | None = None
    segment_4_val: str | None = None
    segment_5_col: str | None = None
    segment_5_op: str | None = None
    segment_5_val: str | None = None
    segment_6_col: str | None = None
    segment_6_op: str | None = None
    segment_6_val: str | None = None
    segment_7_col: str | None = None
    segment_7_op: str | None = None
    segment_7_val: str | None = None
    segment_8_col: str | None = None
    segment_8_op: str | None = None
    segment_8_val: str | None = None
    segment_9_col: str | None = None
    segment_9_op: str | None = None
    segment_9_val: str | None = None
    segment_10_col: str | None = None
    segment_10_op: str | None = None
    segment_10_val: str | None = None
    segment_11_col: str | None = None
    segment_11_op: str | None = None
    segment_11_val: str | None = None
    segment_12_col: str | None = None
    segment_12_op: str | None = None
    segment_12_val: str | None = None
    segment_13_col: str | None = None
    segment_13_op: str | None = None
    segment_13_val: str | None = None
    segment_14_col: str | None = None
    segment_14_op: str | None = None
    segment_14_val: str | None = None
    segment_15_col: str | None = None
    segment_15_op: str | None = None
    segment_15_val: str | None = None
    segment_16_col: str | None = None
    segment_16_op: str | None = None
    segment_16_val: str | None = None
    segment_17_col: str | None = None
    segment_17_op: str | None = None
    segment_17_val: str | None = None
    segment_18_col: str | None = None
    segment_18_op: str | None = None
    segment_18_val: str | None = None
    segment_19_col: str | None = None
    segment_19_op: str | None = None
    segment_19_val: str | None = None
    segment_20_col: str | None = None
    segment_20_op: str | None = None
    segment_20_val: str | None = None

    account_type: AccountType | None = None
    created_by: UserBase | None = None
    updated_by: UserBase | None = None


class ApprovalLimit(BaseModel):
    id: int | None = None
    name: str | None = None
    amount: str | None = None
    subject: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    currency: Currency | None = None
    created_by: UserBase | None = None
    updated_by: UserBase | None = None


class Role(BaseModel):
    id: int | None = None
    name: str | None = None
    description: str | None = None
    omnipotent: bool | None = None
    created_at: str | None = None
    updated_at: str | None = None
    system_role: bool | None = None

    updated_by: UserBase | None = None
    created_by: UserBase | None = None


class UserGroup(BaseModel):
    id: int | None = None
    type: str | None = None
    name: str | None = None
    active: bool | None = None
    open: bool | None = None
    description: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    can_approve: bool | None = None
    mention_name: str | None = None
    avatar_thumb_url: str | None = None

    updated_by: UserBase | None = None
    created_by: UserBase | None = None

    users: list[UserBase] | None = None
    content_groups: list[ContentGroup] | None = None


class LegalEntity(BaseModel):
    id: int | None = None
    name: str | None = None
    abbreviation: str | None = None
    active: bool | None = None
    created_at: str | None = None
    updated_at: str | None = None

    currency: Currency | None = None
    bill_to_address: Address | None = None
    created_by: UserBase | None = None
    updated_by: UserBase | None = None


class User(UserBase):
    id: int | None = None
    login: str | None = None
    email: str | None = None
    firstname: str | None = None
    lastname: str | None = None
    fullname: str | None = None
    employee_number: str | None = None
    salesforce_id: str | None = None
    avatar_thumb_url: str | None = None
    middlename: str | None = None
    active: bool | None = None
    created_at: str | None = None
    updated_at: str | None = None
    purchasing_user: bool | None = None
    expense_user: bool | None = None
    sourcing_user: bool | None = None
    inventory_user: bool | None = None
    contracts_user: bool | None = None
    analytics_user: bool | None = None
    aic_user: bool | None = None
    spend_guard_user: bool | None = None
    ccw_user: bool | None = None
    clm_advanced_user: bool | None = None
    supply_chain_user: bool | None = None
    risk_assess_user: bool | None = None
    travel_user: bool | None = None
    treasury_user: bool | None = None
    api_user: bool | None = None
    account_security_type: int | None = None
    authentication_method: str | None = None
    sso_identifier: str | None = None
    default_locale: str | None = None
    business_group_security_type: int | None = None
    mention_name: str | None = None
    seniority_level: str | None = None
    business_function: str | None = None
    employee_payment_channel: str | None = None
    allow_employee_payment_account_creation: bool | None = None
    category_planner_user: bool | None = None

    custom_fields: UserCustomFields | None = None
    default_account: Account | None = None
    default_account_type: AccountType | None = None
    default_address: Address | None = None
    default_currency: Currency | None = None
    requisition_approval_limit: ApprovalLimit | None = None
    expense_approval_limit: ApprovalLimit | None = None
    invoice_approval_limit: ApprovalLimit | None = None
    contract_approval_limit: ApprovalLimit | None = None
    requisition_self_approval_limit: ApprovalLimit | None = None
    expense_self_approval_limit: ApprovalLimit | None = None
    invoice_self_approval_limit: ApprovalLimit | None = None
    contract_self_approval_limit: ApprovalLimit | None = None
    created_by: UserBase | None = None
    updated_by: UserBase | None = None
    legal_entity: LegalEntity | None = None

    working_warehouses: list[str] | None = None
    inventory_organizations: list[str] | None = None

    roles: list[Role] | None = None
    expenses_delegated_to: list[UserBase] | None = None
    can_expense_for: list[UserBase] | None = None
    content_groups: list[ContentGroup] | None = None
    account_groups: list[AccountGroup] | None = None
    approval_groups: list[UserGroup] | None = None
    user_groups: list[UserGroup] | None = None
