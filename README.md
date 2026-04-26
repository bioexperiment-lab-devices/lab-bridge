# lab_devices_server

VPS provisioning + Docker Compose stack for a small-team JupyterLab server
with chisel reverse-tunnel access for NAT'd lab devices.

See `docs/superpowers/specs/2026-04-26-vps-provisioning-design.md` for the
design.

## Quick start

```bash
task doctor                              # check local prerequisites
cp config.example.yaml config.yaml       # then edit with your VPS details
task secrets:add-user -- alice           # add a JupyterLab user
task secrets:add-client -- microscope-1 9001  # add a lab device
task provision                           # first-time VPS setup
task deploy                              # render configs + bring up stack
```

## Prerequisites (operator laptop)

- [task](https://taskfile.dev)
- [yq v4](https://github.com/mikefarah/yq) (mikefarah, *not* the Python one)
- `htpasswd` (apache2-utils on Linux; included with macOS)
- `openssl`, `ssh`, `rsync`
- For development: `bats-core`, Docker (for the fake-VPS test container)
