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
- paramiko 5.0 dropped `ssh-rsa` from default `Transport._preferred_keys`.
  Servers advertising only `ssh-rsa` (e.g. GlobalSCAPE EFT) fail with
  `IncompatiblePeer: no acceptable host key`. Set `enable_legacy_rsa=True` on
  the resource. Diagnose with `ssh -vv <host>` — the
  `peer server KEXINIT proposal` line shows the offered host-key algorithms.
