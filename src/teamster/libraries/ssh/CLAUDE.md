# CLAUDE.md — `teamster/libraries/ssh/`

Extended SSH/SFTP resource used by every SFTP-based integration. Wraps
`dagster-ssh`'s `SSHResource` with two extra capabilities:

- `listdir_attr_r()` — recursive SFTP directory listing returning
  `(SFTPAttributes, path)` tuples
- `open_ssh_tunnel()` — opens an SSH tunnel via `sshpass` + subprocess, used
  exclusively for the PowerSchool Oracle ODBC connection

## Key Fields Added

| Field                | Type          | Purpose                                                           |
| -------------------- | ------------- | ----------------------------------------------------------------- |
| `tunnel_remote_host` | `str \| None` | Remote bind host for local port forwarding                        |
| `test`               | `bool`        | If `True`, reads SSH password from env var instead of secret file |
| `enable_legacy_rsa`  | `bool`        | Re-enable paramiko's dropped `ssh-rsa` host-key algorithm         |

## Notes

- `SFTPAttributes.st_mtime` and `st_mode` are `int | None` in paramiko's type
  stubs — wrap in `check.not_none()` when comparing
- `open_ssh_tunnel()` is only called by the PowerSchool ODBC library
- In production, the PowerSchool SSH password is read from
  `/etc/secret-volume/powerschool_ssh_password.txt`; in test mode it reads from
  the `password` field directly
- paramiko 5.0 disabled `ssh-rsa` at three independent layers, and ALL three
  must be temporarily re-enabled for a connect against a legacy-only server
  (e.g. GlobalSCAPE EFT 8.1) to succeed:
  1. `Transport._preferred_keys` — KEX negotiation. Skip →
     `IncompatiblePeer: no acceptable host key`.
  2. `Transport._key_info` — algorithm→PKey-class dict consulted by
     `_verify_key` on the server's host key. Skip → `KeyError: 'ssh-rsa'`.
  3. `RSAKey.HASHES` — signature-algorithm→hash dict consulted by
     `verify_ssh_sig`. Skip →
     `SSHException: Signature verification (ssh-rsa) failed`. Map `ssh-rsa` →
     `cryptography.hazmat.primitives.hashes.SHA1`. (paramiko's `rsakey.py:84-87`
     comment explicitly justifies the SHA-1 refusal even while accepting ssh-rsa
     keys.)

  `enable_legacy_rsa=True` on the resource handles all three under a single
  module-level lock. Diagnose new failures progressively: `ssh -vv <host>` shows
  the offered host-key algorithms at the `peer server KEXINIT proposal` line,
  then read the paramiko traceback to identify which of the three layers the
  failure surfaces from.
