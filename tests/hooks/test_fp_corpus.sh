#!/bin/bash
# False-positive corpus for check-output.sh detection (Batch 6, #16-19/#29/#30).
# Every case here is a BENIGN tool output that must NOT be flagged as a secret.
# This is the back-out gauge: any new detection rule that trips one of these is
# too broad and must be tuned or dropped. Keep these realistic.
#
# Usage: bash tests/hooks/test_fp_corpus.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tests/hooks/helpers.sh
source "${SCRIPT_DIR}/helpers.sh"

echo ""
echo "========================================="
echo " FP corpus — benign output must stay clean"
echo "========================================="

echo ""
echo -e "${YELLOW}Code / logs / structured output${NC}"
check_output "git log line" clean "abc1234 feat(x): add retry to loader"
check_output "python code" clean "def hello():
    return {'status': 'ok', 'count': 42}"
check_output "json api response" clean '{"id": 4291, "name": "Newark Lab", "status": "active", "enrollment": 612}'
check_output "dbt run line" clean "1 of 5 OK created sql table model analytics.fct_attendance [SELECT in 2.3s]"
check_output "dagster run id (uuid)" clean "Run 7f3a9c2e-1b4d-4e8a-9c2f-0a1b2c3d4e5f STARTED for asset kipptaf/marts/fct_x"
check_output "config snippet" clean "timeout: 30
retries: 3
log_level: info"
check_output "url with query params" clean "GET https://api.example.com/v1/users?page=2&limit=50&sort=name"
check_output "ls -l output" clean "drwxr-xr-x 5 vscode vscode 4096 Jun  3 10:00 src"

echo ""
echo -e "${YELLOW}Long / high-entropy-looking but benign (#29 risk)${NC}"
check_output "sha256 checksum (64 hex)" clean "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
check_output "sha512 checksum (128 hex)" clean "cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e"
check_output "git commit sha (40 hex)" clean "commit 9b1246a89c0ffee1234567890abcdef12345678"
check_output "data-uri png image (long base64)" clean "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
check_output "uuid list" clean "7f3a9c2e-1b4d-4e8a-9c2f-0a1b2c3d4e5f 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d"
check_output "base64 of benign prose" clean "VGhlIHF1aWNrIGJyb3duIGZveCBqdW1wcyBvdmVyIHRoZSBsYXp5IGRvZyBhbmQgcnVucyBhd2F5"

echo ""
echo -e "${YELLOW}Prose mentioning secret-ish words (#19 generic risk)${NC}"
check_output "prose: set the api key" clean "Set the api_key in your config file before running the loader."
check_output "prose: token expires" clean "The session token expires after 60 minutes; refresh as needed."
check_output "prose: password reset" clean "Click the link to reset your password if you forgot it."
check_output "yaml key with short value" clean "api_key: changeme
log_level: debug"
check_output "env-var name mention" clean "Set GITHUB_TOKEN in CI; the secret is injected at deploy time."

print_summary "FP corpus"
