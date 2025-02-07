#!/bin/bash

openssl genrsa -out env/kipptaf_auth.key 2048

# Leave the Country Name, State or Province Name, Locality Name, and Challenge Password
# fields blank.
#    Organization Name: This MUST be the same string used by your organization when
#        registered with ADP
#    Common Name: This is the company name. Please include “MutualSSL” after the company
#        name. Do not use any special characters.
openssl req -new -key env/kipptaf_auth.key -out env/kipptaf_auth.csr
