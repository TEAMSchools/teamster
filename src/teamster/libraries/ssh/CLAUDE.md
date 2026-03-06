# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

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

## Notes

- `open_ssh_tunnel()` is only called by the PowerSchool ODBC library
- In production, the PowerSchool SSH password is read from
  `/etc/secret-volume/powerschool_ssh_password.txt`; in test mode it reads from
  the `password` field directly
