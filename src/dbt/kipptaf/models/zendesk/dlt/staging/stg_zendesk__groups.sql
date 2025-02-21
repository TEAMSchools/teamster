select id, `name`, from {{ source("zendesk", "groups") }}
