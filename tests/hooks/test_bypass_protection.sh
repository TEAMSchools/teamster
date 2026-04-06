#!/bin/bash
# Tests for bypass detection: 1Password CLI, encoding (base64/xxd/printf),
# process substitution, Python string construction, __import__, importlib,
# /proc access, /dev/fd/.
#
# Usage: bash tests/hooks/test_bypass_detection.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tests/hooks/helpers.sh
source "${SCRIPT_DIR}/helpers.sh"

echo ""
echo "========================================="
echo " Bypass Detection (check-sensitive.sh)"
echo "========================================="

# ─── Pattern 4: 1Password CLI ────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}Pattern 4: 1Password CLI escalation${NC}"

expect_deny "op vault list" Bash command "op vault list"
expect_deny "op item get" Bash command "op item get 'DB Password'"
expect_deny "op double-space vault" Bash command "op  vault list"
expect_deny "op with flags before subcommand" Bash command "op --format json vault list"
expect_deny "op read" Bash command "op read op://vault/item/field"
expect_deny "op document get" Bash command "op document get abc123"
expect_deny "op inject" Bash command "op inject -i template.env"
expect_deny "op run" Bash command "op run --env-file=.env.tpl -- env"
expect_deny "op run with no flags" Bash command "op run -- printenv"

expect_allow "op --version" Bash command "op --version"
expect_allow "op whoami" Bash command "op whoami"
expect_allow "operation word" Bash command "echo operation complete"

# ─── Pattern 5: Encoding-based bypass ─────────────────────────────────────────
echo ""
echo -e "${YELLOW}Pattern 5: Encoding-based bypass detection${NC}"

expect_deny "base64 -d piped to bash" Bash command 'echo cHJpbnRlbnY= | base64 -d | bash'
expect_deny "base64 -d piped to sh" Bash command 'echo cHJpbnRlbnY= | base64 -d | sh'
expect_deny "xxd piped to bash" Bash command 'echo 7072696e74656e76 | xxd -r -p | bash'
expect_deny "printf hex piped to bash" Bash command 'printf "\x70\x72\x69\x6e\x74\x65\x6e\x76" | bash'
expect_deny "base64 --decode piped to bash" Bash command 'echo cHJpbnRlbnY= | base64 --decode | bash'
expect_deny "base64 --decode two-step" Bash command 'base64 --decode payload.b64 > /tmp/x.sh && bash /tmp/x.sh'
expect_deny "printf hex piped to source" Bash command 'printf "\x70\x72" | source /dev/stdin'

expect_deny "base64 two-step via &&" Bash command 'base64 -d payload.b64 > /tmp/x.sh && bash /tmp/x.sh'
expect_deny "base64 two-step via ;" Bash command 'base64 -d payload.b64 > /tmp/x.sh; sh /tmp/x.sh'
expect_deny "xxd two-step via &&" Bash command 'xxd -r -p payload.hex > /tmp/x.sh && bash /tmp/x.sh'

expect_allow "base64 encode (no exec)" Bash command "echo hello | base64"
expect_allow "base64 decode to file" Bash command "base64 -d input.b64 > output.bin"
expect_allow "xxd without pipe to shell" Bash command "xxd file.bin"
expect_allow "printf normal usage" Bash command 'printf "hello %s\n" world'

# ─── Pattern 5a: Process substitution / here-string bypass ───────────────────
echo ""
echo -e "${YELLOW}Pattern 5a: Process substitution / here-string bypass${NC}"

expect_deny "bash <(base64 -d)" Bash command 'bash <(echo cHJpbnRlbnY= | base64 -d)'
expect_deny "sh <(base64 -d)" Bash command 'sh <(echo cHJpbnRlbnY= | base64 -d)'
expect_deny "bash <(xxd)" Bash command 'bash <(echo 7072696e74656e76 | xxd -r -p)'
# test fixture: $() must not expand — value is a literal command string for the hook
# trunk-ignore(shellcheck/SC2016)
expect_deny "bash <<< base64 -d" Bash command 'bash <<< "$(echo cHJpbnRlbnY= | base64 -d)"'
expect_deny "bash <(base64 --decode)" Bash command 'bash <(echo cHJpbnRlbnY= | base64 --decode)'
# test fixture: $() must not expand — value is a literal command string for the hook
# trunk-ignore(shellcheck/SC2016)
expect_deny "bash <<< base64 -d (unquoted)" Bash command 'bash <<< $(echo cHJpbnRlbnY= | base64 -d)'

expect_allow "bash <(echo hello)" Bash command 'bash <(echo "echo hello")'

# ─── Pattern 5b: Python runtime string construction ─────────────────────────
echo ""
echo -e "${YELLOW}Pattern 5b: Python runtime string construction${NC}"

expect_deny "python eval+chr construction" Bash command 'uv run python -c "eval(chr(112)+chr(114))"'
expect_deny "python eval+join construction" Bash command "uv run python -c \"eval(''.join(['import',' os']))\""
expect_deny "python exec+chr construction" Bash command 'uv run python -c "exec(chr(112)+chr(114))"'
expect_deny "python exec+join construction" Bash command "uv run python -c \"exec(''.join(['import',' os']))\""
expect_deny "python exec+bytes construction" Bash command 'uv run python -c "exec(bytes([112,114,105]).decode())"'
expect_deny "exec(base64.b64decode(...))" Bash command 'uv run python -c "import base64; exec(base64.b64decode(b\"cHJpbnRlbnY=\"))"'
expect_deny "exec(codecs.decode(...))" Bash command 'uv run python -c "import codecs; exec(codecs.decode(\"cevagrai\", \"rot13\"))"'
expect_deny "exec(bytes.fromhex(...))" Bash command 'uv run python -c "exec(bytes.fromhex(\"7072696e74656e76\").decode())"'

expect_allow "normal python chr" Bash command 'uv run python -c "print(chr(65))"'
expect_allow "normal python join" Bash command "uv run python -c \"print(','.join(['a','b']))\""
expect_allow "normal python bytes" Bash command 'uv run python -c "print(bytes([65,66]).decode())"'
expect_allow "base64.b64decode without exec" Bash command 'uv run python -c "import base64; print(base64.b64decode(b\"aGVsbG8=\"))"'
expect_allow "codecs.decode without exec" Bash command 'uv run python -c "import codecs; print(codecs.decode(\"uryyb\", \"rot13\"))"'

# ─── Python __import__ bypass ─────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}Python __import__ bypass${NC}"

expect_deny "__import__ os" Bash command "uv run python -c \"__import__('os').popen('id').read()\""
expect_deny "__import__ subprocess" Bash command "uv run python -c \"__import__('subprocess').check_output(['id'])\""
expect_deny "__import__ shutil" Bash command "uv run python -c \"__import__('shutil').copy('/tmp/a','/tmp/b')\""

expect_allow "__import__ json (safe)" Bash command "uv run python -c \"__import__('json').dumps({'a': 1})\""
expect_allow "__import__ math (safe)" Bash command "uv run python -c \"print(__import__('math').pi)\""

# ─── Pattern 5c expanded: additional dangerous modules ───────────────────────
echo ""
echo -e "${YELLOW}Pattern 5c expanded: additional dangerous modules${NC}"

expect_deny "__import__ pty" Bash command "uv run python -c \"__import__('pty').spawn('/bin/bash')\""
expect_deny "__import__ ctypes" Bash command "uv run python -c \"__import__('ctypes').CDLL('libc.so.6')\""
expect_deny "__import__ socket" Bash command "uv run python -c \"__import__('socket').socket()\""
expect_deny "__import__ http" Bash command "uv run python -c \"__import__('http.client').HTTPConnection('x')\""
expect_deny "__import__ urllib" Bash command "uv run python -c \"__import__('urllib.request').urlopen('http://x')\""
expect_deny "__import__ multiprocessing" Bash command "uv run python -c \"__import__('multiprocessing').Process()\""
expect_deny "__import__ signal" Bash command "uv run python -c \"__import__('signal').alarm(0)\""

# ─── Pattern 5d: Python importlib bypass ────────────────────────────────────
echo ""
echo -e "${YELLOW}Pattern 5d: Python importlib bypass${NC}"

expect_deny "importlib os" Bash command "uv run python -c \"import importlib; importlib.import_module('os').system('id')\""
expect_deny "importlib subprocess" Bash command "uv run python -c \"import importlib; importlib.import_module('subprocess').run(['id'])\""
expect_deny "importlib shutil" Bash command "uv run python -c \"import importlib; importlib.import_module('shutil').copy('a','b')\""
expect_allow "importlib json (safe)" Bash command "uv run python -c \"import importlib; importlib.import_module('json').dumps({})\""

expect_deny "importlib pty" Bash command "uv run python -c \"import importlib; importlib.import_module('pty').spawn('/bin/bash')\""
expect_deny "importlib ctypes" Bash command "uv run python -c \"import importlib; importlib.import_module('ctypes')\""
expect_deny "importlib socket" Bash command "uv run python -c \"import importlib; importlib.import_module('socket')\""

# ─── Tool-type scoping: Bash-only rules don't fire for file tools ──────
echo ""
echo -e "${YELLOW}Tool-type scoping: Bash-only rules for file tools${NC}"

expect_allow "Read file named printenv" Read file_path "/tmp/printenv-results.txt"
expect_allow "Read file named op-docs" Read file_path "/tmp/op-vault-docs.txt"
expect_allow "Grep for printenv in code" Grep pattern "printenv"

# ─── Rule 1c: High-risk proc/dev paths (all tools) ──────────────────────
echo ""
echo -e "${YELLOW}Rule 1c: High-risk proc/dev paths (all tools)${NC}"

expect_deny "/proc/self/environ via Read" Read file_path "/proc/self/environ"
expect_deny "/proc/self/cmdline via Read" Read file_path "/proc/self/cmdline"
expect_deny "/proc/1/environ via Bash" Bash command "cat /proc/1/environ"
expect_deny "/dev/fd/ via Read" Read file_path "/dev/fd/3"
expect_deny "/dev/fd/ via Bash" Bash command "cat /dev/fd/3"

print_summary "Bypass Detection"
