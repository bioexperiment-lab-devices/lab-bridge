# VPS Provisioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Taskfile-driven set of bash scripts that provisions an Ubuntu 24.04 VPS over SSH and deploys a JupyterLab + chisel + Caddy Docker Compose stack with per-user basic auth, per-device chisel auth, and short-lived public IP TLS.

**Architecture:** A single gitignored `config.yaml` is the operator's source of truth. Local bash helpers validate it, render three templates (`docker-compose.yml`, `Caddyfile`, `chisel/users.json`) into a staging dir, rsync that to the VPS, and run `docker compose up -d` over SSH. Secrets-management tasks mutate `config.yaml` in place via `yq`. Unit tests use `bats-core` against fixture configs; an Ubuntu-24.04 Docker container with SSHD acts as a "fake VPS" for integration tests.

**Tech Stack:** bash, [go-task](https://taskfile.dev) for the runner, [mikefarah/yq v4](https://github.com/mikefarah/yq) for YAML manipulation, `htpasswd` (apache2-utils) for bcrypt hashing, `openssl` for randomness, `bats-core` for shell tests, Docker + Docker Compose v2 on the VPS.

**Operator-laptop prerequisites** (documented in README; verified by `task doctor` in Task 4): `task`, `yq` (mikefarah v4), `htpasswd`, `openssl`, `ssh`, `rsync`, `bats` (only for development).

---

## File Structure

```
lab_devices_server/
├── .gitignore
├── README.md
├── Taskfile.yml
├── config.example.yaml
├── compose/
│   ├── docker-compose.yml.tmpl
│   ├── Caddyfile.tmpl
│   └── chisel-users.json.tmpl
├── scripts/
│   ├── provision.sh          # idempotent first-time VPS setup (Task 14)
│   ├── deploy.sh             # render + rsync + compose up (Task 15)
│   ├── secrets.sh            # dispatcher for secrets:* subcommands (Task 9-13)
│   ├── ops.sh                # dispatcher for logs/ps/ssh/backup/restart/down/destroy (Task 16)
│   └── lib/
│       ├── common.sh         # log/die/ssh-wrapper (Task 3)
│       ├── config.sh         # load + validate config.yaml (Task 5)
│       ├── render.sh         # render templates (Tasks 6, 7, 8)
│       └── crypto.sh         # bcrypt hashing + password generation (Task 9)
└── tests/
    ├── fixtures/
    │   ├── valid_config.yaml
    │   ├── missing_field_config.yaml
    │   ├── duplicate_port_config.yaml
    │   └── bad_hash_config.yaml
    ├── helpers.bash          # shared bats helpers (mktemp, fixture loading)
    ├── test_config.bats
    ├── test_render.bats
    ├── test_crypto.bats
    ├── test_secrets.bats
    ├── test_provision.bats   # integration; uses fake-VPS container
    ├── test_deploy.bats      # integration; uses fake-VPS container
    └── fake_vps/
        ├── Dockerfile
        └── start.sh
```

**Responsibility boundaries:**

- `lib/*.sh` are pure functions (no SSH, no `docker compose`). Trivially unit-testable.
- `scripts/{provision,deploy,secrets,ops}.sh` orchestrate libs + remote effects.
- `compose/*.tmpl` use placeholder syntax (`__VARNAME__`) — `render.sh` substitutes via `sed`/`yq`. No Go templating runtime, no extra dependency.
- `tests/` mirrors layout: `lib/` → bats files; remote-effecting scripts get a fake-VPS container.

---

## Task 1: Repository scaffolding

**Files:**
- Create: `.gitignore`
- Create: `README.md`

- [ ] **Step 1: Write `.gitignore`**

```
# Operator-private secrets and runtime state
config.yaml
backups/
.task/

# Editor cruft
.DS_Store
*.swp
.idea/
.vscode/
```

- [ ] **Step 2: Write `README.md`** (the content below — copy verbatim, including the inner triple-backtick fences)

````markdown
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
````

- [ ] **Step 3: Commit**

```bash
git add .gitignore README.md
git commit -m "chore: add .gitignore and README"
```

---

## Task 2: `config.example.yaml`

**Files:**
- Create: `config.example.yaml`

- [ ] **Step 1: Write the example config**

```yaml
# config.example.yaml — copy to config.yaml and fill in.
# config.yaml is gitignored; never commit secrets.

vps:
  host: 0.0.0.0                       # public IPv4 of the VPS
  ssh_user: khamit                    # must already exist with passwordless sudo
  ssh_port: 22
  remote_root: /srv/lab_devices_server # where rendered configs land on the VPS
  notebooks_path: /srv/jupyterlab/work # bind-mounted into the jupyter container

caddy:
  acme_email: you@example.com         # for Let's Encrypt registration

jupyter:
  # Pinned for reproducibility. Bump explicitly when you want to upgrade.
  image: quay.io/jupyter/scipy-notebook:2026-04-20

chisel:
  image: jpillora/chisel:1.10.1
  listen_port: 8080                   # PUBLIC: lab-device chisel clients dial in

# JupyterLab basic-auth users. Manage via `task secrets:add-user`.
caddy_users: []
# Example shape (do not commit real hashes):
# caddy_users:
#   - name: alice
#     password_hash: "$2y$14$..."

# Lab devices that connect inbound via chisel. Manage via `task secrets:add-client`.
# Each `reverse_port` is reachable inside the docker network as `chisel:<port>`,
# never published to the host. Each device's chisel credential is restricted to
# only its own port.
chisel_clients: []
# Example shape:
# chisel_clients:
#   - name: microscope-1
#     reverse_port: 9001
#     password: "32-char-random"
```

- [ ] **Step 2: Commit**

```bash
git add config.example.yaml
git commit -m "feat: add config.example.yaml schema"
```

---

## Task 3: `lib/common.sh` — logging, errors, SSH wrapper

**Files:**
- Create: `scripts/lib/common.sh`
- Test: `tests/test_common.bats`
- Create: `tests/helpers.bash`

- [ ] **Step 1: Write the test helper**

`tests/helpers.bash`:

```bash
# Source from the repo root regardless of where bats was invoked.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

setup_tmpdir() {
    TMPDIR="$(mktemp -d)"
    export TMPDIR
}

teardown_tmpdir() {
    [[ -n "${TMPDIR:-}" && -d "$TMPDIR" ]] && rm -rf "$TMPDIR"
}

fixture() {
    cat "$ROOT/tests/fixtures/$1"
}
```

- [ ] **Step 2: Write the failing tests**

`tests/test_common.bats`:

```bash
#!/usr/bin/env bats

load helpers

setup() { setup_tmpdir; }
teardown() { teardown_tmpdir; }

@test "log prints a green tagged line to stderr" {
    run bash -c "source $ROOT/scripts/lib/common.sh; log hello 2>&1 1>/dev/null"
    [ "$status" -eq 0 ]
    [[ "$output" == *"hello"* ]]
    [[ "$output" == *"[lab]"* ]]
}

@test "warn prints a yellow tagged line to stderr" {
    run bash -c "source $ROOT/scripts/lib/common.sh; warn careful 2>&1 1>/dev/null"
    [ "$status" -eq 0 ]
    [[ "$output" == *"careful"* ]]
    [[ "$output" == *"[warn]"* ]]
}

@test "die prints to stderr and exits non-zero" {
    run bash -c "source $ROOT/scripts/lib/common.sh; die nope"
    [ "$status" -ne 0 ]
    [[ "$output" == *"nope"* ]]
}

@test "require_cmd succeeds when command exists" {
    run bash -c "source $ROOT/scripts/lib/common.sh; require_cmd ls"
    [ "$status" -eq 0 ]
}

@test "require_cmd fails when command missing" {
    run bash -c "source $ROOT/scripts/lib/common.sh; require_cmd definitely_not_a_command_xyz"
    [ "$status" -ne 0 ]
    [[ "$output" == *"definitely_not_a_command_xyz"* ]]
}
```

- [ ] **Step 3: Run the tests, verify they fail**

```bash
bats tests/test_common.bats
```

Expected: all five fail with "No such file or directory" or sourcing errors.

- [ ] **Step 4: Implement `scripts/lib/common.sh`**

```bash
#!/usr/bin/env bash
# Common helpers: logging, error handling, SSH wrappers.
# Sourced (not executed) by other scripts. Always set strict mode in callers.

if [[ -t 2 ]]; then
    _C_RESET=$'\033[0m'
    _C_GREEN=$'\033[32m'
    _C_YELLOW=$'\033[33m'
    _C_RED=$'\033[31m'
else
    _C_RESET="" _C_GREEN="" _C_YELLOW="" _C_RED=""
fi

log()  { printf '%s[lab]%s %s\n' "$_C_GREEN" "$_C_RESET" "$*" >&2; }
warn() { printf '%s[warn]%s %s\n' "$_C_YELLOW" "$_C_RESET" "$*" >&2; }
die()  { printf '%s[fail]%s %s\n' "$_C_RED" "$_C_RESET" "$*" >&2; exit 1; }

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

# Build the SSH command for the configured VPS. Reads VPS_HOST, VPS_SSH_USER,
# VPS_SSH_PORT from the environment (set by config.sh::load_config).
ssh_cmd() {
    printf 'ssh -p %s -o BatchMode=yes -o ConnectTimeout=10 %s@%s' \
        "${VPS_SSH_PORT:?}" "${VPS_SSH_USER:?}" "${VPS_HOST:?}"
}

# Run a command on the VPS over SSH. Args become a single shell string.
ssh_run() {
    local cmd
    cmd="$(ssh_cmd)"
    # shellcheck disable=SC2086
    $cmd "$@"
}
```

- [ ] **Step 5: Run the tests, verify they pass**

```bash
bats tests/test_common.bats
```

Expected: 5 passing.

- [ ] **Step 6: Commit**

```bash
git add scripts/lib/common.sh tests/test_common.bats tests/helpers.bash
git commit -m "feat(lib): add common.sh logging, errors, and SSH wrapper"
```

---

## Task 4: Taskfile skeleton with `doctor`

**Files:**
- Create: `Taskfile.yml`
- Create: `tests/fixtures/.gitkeep`
- Test: manual smoke-test (Taskfile is data, not logic)

- [ ] **Step 1: Write the Taskfile skeleton**

```yaml
version: '3'

vars:
  CONFIG: config.yaml

tasks:
  default:
    desc: List available tasks
    cmd: task --list

  doctor:
    desc: Verify local prerequisites are installed
    cmds:
      - bash scripts/doctor.sh

  # --- Lifecycle (filled in by later tasks) ---
  provision: { desc: "(stub) Provision a fresh VPS",        cmd: "echo not implemented; exit 1" }
  deploy:    { desc: "(stub) Render configs and deploy",    cmd: "echo not implemented; exit 1" }
  restart:   { desc: "(stub) docker compose restart",        cmd: "echo not implemented; exit 1" }
  down:      { desc: "(stub) docker compose down",           cmd: "echo not implemented; exit 1" }
  destroy:   { desc: "(stub) docker compose down -v",        cmd: "echo not implemented; exit 1" }

  # --- Secrets (filled in by later tasks) ---
  "secrets:add-user":          { desc: "(stub)", cmd: "echo not implemented; exit 1" }
  "secrets:set-user-password": { desc: "(stub)", cmd: "echo not implemented; exit 1" }
  "secrets:rm-user":           { desc: "(stub)", cmd: "echo not implemented; exit 1" }
  "secrets:add-client":        { desc: "(stub)", cmd: "echo not implemented; exit 1" }
  "secrets:show-client":       { desc: "(stub)", cmd: "echo not implemented; exit 1" }
  "secrets:rm-client":         { desc: "(stub)", cmd: "echo not implemented; exit 1" }

  # --- Operations (filled in by later tasks) ---
  logs:    { desc: "(stub)", cmd: "echo not implemented; exit 1" }
  ps:      { desc: "(stub)", cmd: "echo not implemented; exit 1" }
  ssh:     { desc: "(stub)", cmd: "echo not implemented; exit 1" }
  backup:  { desc: "(stub)", cmd: "echo not implemented; exit 1" }
```

- [ ] **Step 2: Write `scripts/doctor.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

missing=0
for cmd in task yq htpasswd openssl ssh rsync; do
    if command -v "$cmd" >/dev/null 2>&1; then
        log "$cmd ✓"
    else
        warn "$cmd ✗ (missing)"
        missing=1
    fi
done

# yq must be the mikefarah Go variant (v4+); detect by --version output.
if command -v yq >/dev/null 2>&1; then
    if yq --version 2>&1 | grep -qE 'mikefarah|version v?[4-9]'; then
        log "yq is mikefarah v4+ ✓"
    else
        warn "yq is present but does not look like mikefarah v4+ — install from https://github.com/mikefarah/yq"
        missing=1
    fi
fi

[[ "$missing" -eq 0 ]] || die "missing prerequisites — see README"
log "all prerequisites present"
```

- [ ] **Step 3: Smoke-test**

```bash
chmod +x scripts/doctor.sh
task --list
task doctor
```

Expected: `task --list` shows all task names; `task doctor` reports each tool with ✓ or ✗ and exits 0 if everything is installed.

- [ ] **Step 4: Commit**

```bash
git add Taskfile.yml scripts/doctor.sh
git commit -m "feat: add Taskfile skeleton and doctor task"
```

---

## Task 5: `lib/config.sh` — load and validate `config.yaml`

**Files:**
- Create: `scripts/lib/config.sh`
- Create: `tests/fixtures/valid_config.yaml`
- Create: `tests/fixtures/missing_field_config.yaml`
- Create: `tests/fixtures/duplicate_port_config.yaml`
- Create: `tests/fixtures/bad_hash_config.yaml`
- Test: `tests/test_config.bats`

- [ ] **Step 1: Write the fixtures**

`tests/fixtures/valid_config.yaml`:

```yaml
vps:
  host: 192.0.2.10
  ssh_user: khamit
  ssh_port: 22
  remote_root: /srv/lab_devices_server
  notebooks_path: /srv/jupyterlab/work
caddy:
  acme_email: ops@example.com
jupyter:
  image: quay.io/jupyter/scipy-notebook:2026-04-20
chisel:
  image: jpillora/chisel:1.10.1
  listen_port: 8080
caddy_users:
  - name: alice
    password_hash: "$2y$14$abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWX"
chisel_clients:
  - name: microscope-1
    reverse_port: 9001
    password: "k7HfLpNqRsT3uVwX1yZ2aB3cD4eF5gH6"
```

`tests/fixtures/missing_field_config.yaml`:

```yaml
vps:
  host: 192.0.2.10
  ssh_user: khamit
  ssh_port: 22
  # remote_root and notebooks_path missing
caddy:
  acme_email: ops@example.com
jupyter:
  image: quay.io/jupyter/scipy-notebook:2026-04-20
chisel:
  image: jpillora/chisel:1.10.1
  listen_port: 8080
caddy_users: []
chisel_clients: []
```

`tests/fixtures/duplicate_port_config.yaml`:

```yaml
vps: {host: 192.0.2.10, ssh_user: khamit, ssh_port: 22, remote_root: /srv/x, notebooks_path: /srv/y}
caddy: {acme_email: ops@example.com}
jupyter: {image: quay.io/jupyter/scipy-notebook:2026-04-20}
chisel: {image: jpillora/chisel:1.10.1, listen_port: 8080}
caddy_users: []
chisel_clients:
  - {name: a, reverse_port: 9001, password: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa}
  - {name: b, reverse_port: 9001, password: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb}
```

`tests/fixtures/bad_hash_config.yaml`:

```yaml
vps: {host: 192.0.2.10, ssh_user: khamit, ssh_port: 22, remote_root: /srv/x, notebooks_path: /srv/y}
caddy: {acme_email: ops@example.com}
jupyter: {image: quay.io/jupyter/scipy-notebook:2026-04-20}
chisel: {image: jpillora/chisel:1.10.1, listen_port: 8080}
caddy_users:
  - {name: alice, password_hash: "not-a-bcrypt-hash"}
chisel_clients: []
```

- [ ] **Step 2: Write the failing tests**

`tests/test_config.bats`:

```bash
#!/usr/bin/env bats

load helpers

setup() { setup_tmpdir; }
teardown() { teardown_tmpdir; }

@test "validate_config: accepts a valid config" {
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $ROOT/tests/fixtures/valid_config.yaml"
    [ "$status" -eq 0 ]
}

@test "validate_config: rejects config missing required fields" {
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $ROOT/tests/fixtures/missing_field_config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"vps.remote_root"* ]]
    [[ "$output" == *"vps.notebooks_path"* ]]
}

@test "validate_config: rejects duplicate chisel reverse_ports" {
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $ROOT/tests/fixtures/duplicate_port_config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"duplicate"* ]] || [[ "$output" == *"9001"* ]]
}

@test "validate_config: rejects non-bcrypt password_hash" {
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $ROOT/tests/fixtures/bad_hash_config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"password_hash"* ]] || [[ "$output" == *"bcrypt"* ]]
}

@test "validate_config: missing file gives clear error" {
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/nope.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"not found"* ]] || [[ "$output" == *"nope.yaml"* ]]
}

@test "load_config: exports VPS_HOST etc." {
    run bash -c "source $ROOT/scripts/lib/config.sh; load_config $ROOT/tests/fixtures/valid_config.yaml; echo \$VPS_HOST \$VPS_SSH_USER \$VPS_SSH_PORT"
    [ "$status" -eq 0 ]
    [[ "$output" == *"192.0.2.10 khamit 22"* ]]
}
```

- [ ] **Step 3: Run tests — verify all fail**

```bash
bats tests/test_config.bats
```

Expected: 6 failing tests.

- [ ] **Step 4: Implement `scripts/lib/config.sh`**

```bash
#!/usr/bin/env bash
# Load and validate config.yaml. Sourced, not executed.
# Depends on lib/common.sh being sourced first.

# Required fields (dot-paths in yq syntax). Each must be a non-empty scalar.
_REQUIRED_FIELDS=(
    .vps.host
    .vps.ssh_user
    .vps.ssh_port
    .vps.remote_root
    .vps.notebooks_path
    .caddy.acme_email
    .jupyter.image
    .chisel.image
    .chisel.listen_port
)

_yq() { yq "$@" 2>/dev/null; }

# validate_config <path> — print all problems to stderr, exit non-zero on any.
validate_config() {
    local path="${1:?validate_config: missing path arg}"
    local errors=()

    if [[ ! -f "$path" ]]; then
        printf 'config not found: %s\n' "$path" >&2
        return 1
    fi

    # Parse-ability check.
    if ! _yq e '.' "$path" >/dev/null; then
        printf 'config is not valid YAML: %s\n' "$path" >&2
        return 1
    fi

    # Required scalar fields.
    local field val
    for field in "${_REQUIRED_FIELDS[@]}"; do
        val="$(_yq e "$field // \"\"" "$path")"
        if [[ -z "$val" || "$val" == "null" ]]; then
            errors+=("missing required field: ${field#.}")
        fi
    done

    # caddy_users password_hash format check (bcrypt: $2[aby]$NN$<53 chars>).
    local i name hash
    local count
    count="$(_yq e '.caddy_users | length' "$path")"
    for ((i=0; i<count; i++)); do
        name="$(_yq e ".caddy_users[$i].name" "$path")"
        hash="$(_yq e ".caddy_users[$i].password_hash" "$path")"
        if [[ -z "$name" || "$name" == "null" ]]; then
            errors+=("caddy_users[$i].name is empty")
        fi
        if ! [[ "$hash" =~ ^\$2[aby]\$[0-9]{2}\$.{53}$ ]]; then
            errors+=("caddy_users[$i].password_hash is not a valid bcrypt hash")
        fi
    done

    # chisel_clients: per-entry validity + duplicate-port check.
    count="$(_yq e '.chisel_clients | length' "$path")"
    local seen_ports=() port pwd
    for ((i=0; i<count; i++)); do
        name="$(_yq e ".chisel_clients[$i].name" "$path")"
        port="$(_yq e ".chisel_clients[$i].reverse_port" "$path")"
        pwd="$(_yq e ".chisel_clients[$i].password" "$path")"
        [[ -z "$name" || "$name" == "null" ]] && errors+=("chisel_clients[$i].name is empty")
        [[ -z "$port" || "$port" == "null" ]] && errors+=("chisel_clients[$i].reverse_port is empty")
        [[ -z "$pwd"  || "$pwd"  == "null" ]] && errors+=("chisel_clients[$i].password is empty")
        if [[ -n "$port" && "$port" != "null" ]]; then
            for seen in "${seen_ports[@]:-}"; do
                [[ "$seen" == "$port" ]] && errors+=("chisel_clients: duplicate reverse_port $port")
            done
            seen_ports+=("$port")
        fi
    done

    if (( ${#errors[@]} > 0 )); then
        printf 'config validation failed:\n' >&2
        printf '  - %s\n' "${errors[@]}" >&2
        return 1
    fi
    return 0
}

# load_config <path> — validate, then export VPS_*, CADDY_*, etc. for later use.
load_config() {
    local path="${1:?load_config: missing path arg}"
    validate_config "$path" || return 1
    export CONFIG_PATH="$path"
    export VPS_HOST          ; VPS_HOST="$(_yq e '.vps.host' "$path")"
    export VPS_SSH_USER      ; VPS_SSH_USER="$(_yq e '.vps.ssh_user' "$path")"
    export VPS_SSH_PORT      ; VPS_SSH_PORT="$(_yq e '.vps.ssh_port' "$path")"
    export VPS_REMOTE_ROOT   ; VPS_REMOTE_ROOT="$(_yq e '.vps.remote_root' "$path")"
    export VPS_NOTEBOOKS_PATH; VPS_NOTEBOOKS_PATH="$(_yq e '.vps.notebooks_path' "$path")"
    export CADDY_ACME_EMAIL  ; CADDY_ACME_EMAIL="$(_yq e '.caddy.acme_email' "$path")"
    export JUPYTER_IMAGE     ; JUPYTER_IMAGE="$(_yq e '.jupyter.image' "$path")"
    export CHISEL_IMAGE      ; CHISEL_IMAGE="$(_yq e '.chisel.image' "$path")"
    export CHISEL_LISTEN_PORT; CHISEL_LISTEN_PORT="$(_yq e '.chisel.listen_port' "$path")"
}
```

- [ ] **Step 5: Run tests — verify all pass**

```bash
bats tests/test_config.bats
```

Expected: 6 passing.

- [ ] **Step 6: Commit**

```bash
git add scripts/lib/config.sh tests/test_config.bats tests/fixtures/
git commit -m "feat(lib): add config.sh with validation and load"
```

---

## Task 6: `compose/docker-compose.yml.tmpl` + `render_compose`

**Files:**
- Create: `compose/docker-compose.yml.tmpl`
- Create: `scripts/lib/render.sh`
- Test: `tests/test_render.bats`

- [ ] **Step 1: Write the compose template**

`compose/docker-compose.yml.tmpl` (placeholders are `__NAME__`):

```yaml
services:
  caddy:
    image: caddy:2
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./caddy_data:/data
      - ./caddy_config:/config
    networks: [labnet]
    depends_on: [jupyter]

  jupyter:
    image: __JUPYTER_IMAGE__
    restart: unless-stopped
    command:
      - start-notebook.sh
      - --ServerApp.token=
      - --ServerApp.password=
      - --ServerApp.allow_origin=*
      - --ServerApp.base_url=/
    volumes:
      - __NOTEBOOKS_PATH__:/home/jovyan/work
    networks: [labnet]
    # No `ports:` — only Caddy reaches it as jupyter:8888 on labnet.

  chisel:
    image: __CHISEL_IMAGE__
    restart: unless-stopped
    command:
      - server
      - --port=__CHISEL_LISTEN_PORT__
      - --authfile=/etc/chisel/users.json
      - --reverse
    ports:
      - "__CHISEL_LISTEN_PORT__:__CHISEL_LISTEN_PORT__"
    volumes:
      - ./chisel/users.json:/etc/chisel/users.json:ro
    networks: [labnet]

networks:
  labnet:
    driver: bridge
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_render.bats`:

```bash
#!/usr/bin/env bats

load helpers

setup() { setup_tmpdir; }
teardown() { teardown_tmpdir; }

@test "render_compose: substitutes image, paths, and chisel port" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
        cat $TMPDIR/docker-compose.yml
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"image: quay.io/jupyter/scipy-notebook:2026-04-20"* ]]
    [[ "$output" == *"image: jpillora/chisel:1.10.1"* ]]
    [[ "$output" == *"/srv/jupyterlab/work:/home/jovyan/work"* ]]
    [[ "$output" == *"--port=8080"* ]]
    [[ "$output" == *'"8080:8080"'* ]]
    [[ "$output" != *"__"*"__"* ]]   # no leftover placeholders
}
```

- [ ] **Step 3: Run the test, verify it fails**

```bash
bats tests/test_render.bats
```

Expected: 1 failing test ("render_compose: command not found" or similar).

- [ ] **Step 4: Implement `render_compose` in `scripts/lib/render.sh`**

```bash
#!/usr/bin/env bash
# Render the three deploy templates into a staging directory.
# Sourced, not executed. Depends on common.sh + config.sh being sourced and
# load_config having been called.

# render_compose <template_path> <output_path>
render_compose() {
    local tmpl="${1:?}" out="${2:?}"
    [[ -f "$tmpl" ]] || die "template not found: $tmpl"
    sed \
        -e "s|__JUPYTER_IMAGE__|${JUPYTER_IMAGE:?}|g" \
        -e "s|__CHISEL_IMAGE__|${CHISEL_IMAGE:?}|g" \
        -e "s|__CHISEL_LISTEN_PORT__|${CHISEL_LISTEN_PORT:?}|g" \
        -e "s|__NOTEBOOKS_PATH__|${VPS_NOTEBOOKS_PATH:?}|g" \
        "$tmpl" > "$out"
}
```

- [ ] **Step 5: Run tests, verify pass**

```bash
bats tests/test_render.bats
```

Expected: 1 passing.

- [ ] **Step 6: Commit**

```bash
git add compose/docker-compose.yml.tmpl scripts/lib/render.sh tests/test_render.bats
git commit -m "feat(render): render docker-compose.yml from template"
```

---

## Task 7: `compose/Caddyfile.tmpl` + `render_caddyfile`

**Files:**
- Create: `compose/Caddyfile.tmpl`
- Modify: `scripts/lib/render.sh`
- Modify: `tests/test_render.bats`

- [ ] **Step 1: Write the Caddyfile template**

`compose/Caddyfile.tmpl`:

```
{
    email __ACME_EMAIL__
}

https://__VPS_HOST__ {
    tls {
        issuer acme {
            profile shortlived
        }
        issuer internal
    }

    basic_auth {
__BASIC_AUTH_BLOCK__
    }

    reverse_proxy jupyter:8888
}
```

The `__BASIC_AUTH_BLOCK__` placeholder is replaced with one indented `<name> <hash>` line per `caddy_users` entry. Caddy's `basic_auth` directive accepts inline `username password_hash` pairs.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_render.bats`:

```bash
@test "render_caddyfile: includes IP, email, basic_auth, and reverse_proxy" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_caddyfile $ROOT/compose/Caddyfile.tmpl $TMPDIR/Caddyfile
        cat $TMPDIR/Caddyfile
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"https://192.0.2.10"* ]]
    [[ "$output" == *"email ops@example.com"* ]]
    [[ "$output" == *"alice "*'$2y$14$abcdefghij'* ]]
    [[ "$output" == *"reverse_proxy jupyter:8888"* ]]
    [[ "$output" == *"profile shortlived"* ]]
    [[ "$output" == *"issuer internal"* ]]
    [[ "$output" != *"__"*"__"* ]]
}

@test "render_caddyfile: empty caddy_users yields valid empty basic_auth block" {
    cat > $TMPDIR/empty_users.yaml <<'EOF'
vps: {host: 1.2.3.4, ssh_user: u, ssh_port: 22, remote_root: /srv/x, notebooks_path: /srv/y}
caddy: {acme_email: o@x.io}
jupyter: {image: quay.io/jupyter/scipy-notebook:2026-04-20}
chisel: {image: jpillora/chisel:1.10.1, listen_port: 8080}
caddy_users: []
chisel_clients: []
EOF
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $TMPDIR/empty_users.yaml
        render_caddyfile $ROOT/compose/Caddyfile.tmpl $TMPDIR/Caddyfile
    "
    [ "$status" -eq 0 ]
    # basic_auth block exists but is empty — no users will be able to log in.
    grep -q 'basic_auth {' $TMPDIR/Caddyfile
}
```

- [ ] **Step 3: Run tests, verify both fail**

```bash
bats tests/test_render.bats
```

Expected: 2 new tests fail.

- [ ] **Step 4: Add `render_caddyfile` to `scripts/lib/render.sh`**

Append:

```bash
# render_caddyfile <template_path> <output_path>
render_caddyfile() {
    local tmpl="${1:?}" out="${2:?}"
    [[ -f "$tmpl" ]] || die "template not found: $tmpl"

    local block name hash count i
    block=""
    count="$(yq e '.caddy_users | length' "${CONFIG_PATH:?}")"
    for ((i=0; i<count; i++)); do
        name="$(yq e ".caddy_users[$i].name" "$CONFIG_PATH")"
        hash="$(yq e ".caddy_users[$i].password_hash" "$CONFIG_PATH")"
        block+="        $name $hash"$'\n'
    done
    # Strip trailing newline so the output stays tidy.
    block="${block%$'\n'}"

    awk -v acme="$CADDY_ACME_EMAIL" \
        -v host="$VPS_HOST" \
        -v block="$block" '
        {
            gsub(/__ACME_EMAIL__/, acme)
            gsub(/__VPS_HOST__/, host)
            if ($0 == "__BASIC_AUTH_BLOCK__") {
                print block
                next
            }
            print
        }
    ' "$tmpl" > "$out"
}
```

We use `awk` rather than `sed` because the basic_auth block may contain `$` and `/` characters from bcrypt hashes that would otherwise need escaping in `sed`.

- [ ] **Step 5: Run tests, verify pass**

```bash
bats tests/test_render.bats
```

Expected: 3 passing.

- [ ] **Step 6: Commit**

```bash
git add compose/Caddyfile.tmpl scripts/lib/render.sh tests/test_render.bats
git commit -m "feat(render): render Caddyfile with basic_auth from caddy_users"
```

---

## Task 8: `compose/chisel-users.json.tmpl` + `render_chisel_users`

**Files:**
- Create: `compose/chisel-users.json.tmpl` (purely documentation; rendering is fully programmatic)
- Modify: `scripts/lib/render.sh`
- Modify: `tests/test_render.bats`

- [ ] **Step 1: Write the template stub (for documentation)**

`compose/chisel-users.json.tmpl`:

```
# This file is rendered programmatically by render_chisel_users in
# scripts/lib/render.sh — there is no in-place placeholder substitution.
# Output shape:
# {
#   "<name>:<password>": ["R:0.0.0.0:<reverse_port>"],
#   ...
# }
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_render.bats`:

```bash
@test "render_chisel_users: emits one entry per chisel_clients with route restriction" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_chisel_users $TMPDIR/users.json
        cat $TMPDIR/users.json
    "
    [ "$status" -eq 0 ]
    # Valid JSON?
    echo "$output" | yq -p json e '.' >/dev/null
    [[ "$output" == *'"microscope-1:k7HfLpNqRsT3uVwX1yZ2aB3cD4eF5gH6"'* ]]
    [[ "$output" == *'R:0.0.0.0:9001'* ]]
}

@test "render_chisel_users: empty chisel_clients yields empty object" {
    cat > $TMPDIR/empty.yaml <<'EOF'
vps: {host: 1.2.3.4, ssh_user: u, ssh_port: 22, remote_root: /srv/x, notebooks_path: /srv/y}
caddy: {acme_email: o@x.io}
jupyter: {image: quay.io/jupyter/scipy-notebook:2026-04-20}
chisel: {image: jpillora/chisel:1.10.1, listen_port: 8080}
caddy_users: []
chisel_clients: []
EOF
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $TMPDIR/empty.yaml
        render_chisel_users $TMPDIR/users.json
        cat $TMPDIR/users.json
    "
    [ "$status" -eq 0 ]
    [[ "$(echo "$output" | tr -d '[:space:]')" == "{}" ]]
}
```

- [ ] **Step 3: Run tests — verify both fail**

```bash
bats tests/test_render.bats
```

- [ ] **Step 4: Add `render_chisel_users` to `scripts/lib/render.sh`**

Append:

```bash
# render_chisel_users <output_path>
# Builds the chisel users.json from .chisel_clients in CONFIG_PATH.
render_chisel_users() {
    local out="${1:?}"
    yq -o=json e '
        .chisel_clients
        | map({(.name + ":" + .password): ["R:0.0.0.0:" + (.reverse_port | tostring)]})
        | (. // [{}])
        | .[] as $item ireduce ({}; . * $item)
    ' "${CONFIG_PATH:?}" > "$out"
}
```

A few notes on the yq expression:
- We map each entry to a single-key object whose key is `<name>:<password>` and whose value is the route list.
- `ireduce` merges all those single-key objects into one. The `(. // [{}])` ensures the merge has at least one base object to start from when the list is empty.
- yq's `-o=json` flag emits JSON instead of YAML.

- [ ] **Step 5: Run tests — verify pass**

```bash
bats tests/test_render.bats
```

Expected: 5 passing total.

- [ ] **Step 6: Commit**

```bash
git add compose/chisel-users.json.tmpl scripts/lib/render.sh tests/test_render.bats
git commit -m "feat(render): render chisel users.json with route restrictions"
```

---

## Task 9: `lib/crypto.sh` — bcrypt hashing and password generation

**Files:**
- Create: `scripts/lib/crypto.sh`
- Test: `tests/test_crypto.bats`

- [ ] **Step 1: Write the failing tests**

`tests/test_crypto.bats`:

```bash
#!/usr/bin/env bats

load helpers

@test "gen_password: produces 32 base64 characters (no padding)" {
    run bash -c "source $ROOT/scripts/lib/crypto.sh; gen_password"
    [ "$status" -eq 0 ]
    [[ "${#output}" -eq 32 ]]
    [[ "$output" =~ ^[A-Za-z0-9+/]+$ ]]
}

@test "gen_password: two consecutive calls yield different output" {
    a="$(bash -c "source $ROOT/scripts/lib/crypto.sh; gen_password")"
    b="$(bash -c "source $ROOT/scripts/lib/crypto.sh; gen_password")"
    [[ "$a" != "$b" ]]
}

@test "bcrypt_hash: produces a \$2y\$14\$ hash" {
    run bash -c "source $ROOT/scripts/lib/crypto.sh; bcrypt_hash hunter2"
    [ "$status" -eq 0 ]
    [[ "$output" =~ ^\$2y\$14\$.{53}$ ]]
}

@test "bcrypt_hash: same plaintext, different runs produce different hashes (random salt)" {
    a="$(bash -c "source $ROOT/scripts/lib/crypto.sh; bcrypt_hash hunter2")"
    b="$(bash -c "source $ROOT/scripts/lib/crypto.sh; bcrypt_hash hunter2")"
    [[ "$a" != "$b" ]]
}
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
bats tests/test_crypto.bats
```

- [ ] **Step 3: Implement `scripts/lib/crypto.sh`**

```bash
#!/usr/bin/env bash
# Crypto helpers for secrets management. Sourced, not executed.

# gen_password — print a 32-char base64 password (24 random bytes), no padding.
gen_password() {
    # `tr -d '='` strips base64 padding; `head -c 32` makes it length-stable
    # in case base64 produces a longer line (it shouldn't, but be defensive).
    openssl rand -base64 24 | tr -d '\n=' | head -c 32
    echo
}

# bcrypt_hash <plaintext> — print a bcrypt hash with cost 14 ($2y$ flavor).
bcrypt_hash() {
    local plaintext="${1:?bcrypt_hash: missing plaintext}"
    # htpasswd -nbB <user> <password> emits "user:hash". We use a dummy user
    # and strip the prefix. -B selects bcrypt, -C 14 sets the cost.
    htpasswd -nbBC 14 _ "$plaintext" | sed -e 's/^_://' -e 's/[[:space:]]*$//'
}
```

- [ ] **Step 4: Run tests — verify pass**

```bash
bats tests/test_crypto.bats
```

Expected: 4 passing.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/crypto.sh tests/test_crypto.bats
git commit -m "feat(lib): add crypto.sh with gen_password and bcrypt_hash"
```

---

## Task 10: `secrets:add-user` command

**Files:**
- Create: `scripts/secrets.sh`
- Modify: `Taskfile.yml`
- Test: `tests/test_secrets.bats`

- [ ] **Step 1: Write the failing tests**

`tests/test_secrets.bats`:

```bash
#!/usr/bin/env bats

load helpers

setup() {
    setup_tmpdir
    cp "$ROOT/tests/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
}
teardown() { teardown_tmpdir; }

@test "secrets add-user: appends entry with a bcrypt hash" {
    run bash -c "echo -e 'sekret\nsekret' | $ROOT/scripts/secrets.sh add-user bob"
    [ "$status" -eq 0 ]
    name="$(yq e '.caddy_users[] | select(.name == \"bob\") | .name' "$LDS_CONFIG")"
    hash="$(yq e '.caddy_users[] | select(.name == \"bob\") | .password_hash' "$LDS_CONFIG")"
    [[ "$name" == "bob" ]]
    [[ "$hash" =~ ^\$2y\$14\$.{53}$ ]]
}

@test "secrets add-user: refuses duplicate username" {
    # alice already exists in the fixture
    run bash -c "echo -e 'sekret\nsekret' | $ROOT/scripts/secrets.sh add-user alice"
    [ "$status" -ne 0 ]
    [[ "$output" == *"alice"* ]]
    [[ "$output" == *"exists"* ]] || [[ "$output" == *"already"* ]]
}

@test "secrets add-user: refuses mismatched password confirmation" {
    run bash -c "echo -e 'one\ntwo' | $ROOT/scripts/secrets.sh add-user carol"
    [ "$status" -ne 0 ]
    [[ "$output" == *"match"* ]] || [[ "$output" == *"mismatch"* ]]
}
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
bats tests/test_secrets.bats
```

- [ ] **Step 3: Implement `scripts/secrets.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=lib/config.sh
source "$SCRIPT_DIR/lib/config.sh"
# shellcheck source=lib/crypto.sh
source "$SCRIPT_DIR/lib/crypto.sh"

# Path to config.yaml — overridable for tests.
CONFIG="${LDS_CONFIG:-$SCRIPT_DIR/../config.yaml}"

ensure_config() {
    if [[ ! -f "$CONFIG" ]]; then
        die "config not found: $CONFIG (run: cp config.example.yaml config.yaml)"
    fi
}

prompt_password() {
    # Note: every output here goes to stderr — only the final printf hits
    # stdout, because callers use $(prompt_password ...) to capture the value.
    local label="$1" pw1 pw2
    read -rsp "$label: " pw1
    echo >&2
    read -rsp "$label (again): " pw2
    echo >&2
    [[ "$pw1" == "$pw2" ]] || die "passwords do not match"
    [[ -n "$pw1" ]] || die "empty password"
    printf '%s' "$pw1"
}

cmd_add_user() {
    local name="${1:?usage: secrets.sh add-user <name>}"
    ensure_config

    local existing
    existing="$(yq e ".caddy_users[] | select(.name == \"$name\") | .name" "$CONFIG")"
    [[ -z "$existing" ]] || die "user $name already exists (use set-user-password to rotate)"

    local pw hash
    pw="$(prompt_password "Password for $name")"
    hash="$(bcrypt_hash "$pw")"
    yq -i ".caddy_users += [{\"name\": \"$name\", \"password_hash\": \"$hash\"}]" "$CONFIG"
    log "added user $name"
}

main() {
    local sub="${1:-}"; shift || true
    case "$sub" in
        add-user) cmd_add_user "$@" ;;
        *) die "unknown subcommand: $sub" ;;
    esac
}

main "$@"
```

- [ ] **Step 4: Wire into `Taskfile.yml`**

Replace the `secrets:add-user` stub:

```yaml
  "secrets:add-user":
    desc: Add a JupyterLab user (prompts for password)
    cmd: bash scripts/secrets.sh add-user {{.CLI_ARGS}}
```

- [ ] **Step 5: Run tests — verify pass**

```bash
bats tests/test_secrets.bats
```

Expected: 3 passing.

- [ ] **Step 6: Smoke-test from the Taskfile**

```bash
cp config.example.yaml config.yaml
echo -e 'hunter2\nhunter2' | task secrets:add-user -- alice
yq e '.caddy_users' config.yaml
rm config.yaml
```

Expected: alice's entry present with a `$2y$14$...` hash.

- [ ] **Step 7: Commit**

```bash
git add scripts/secrets.sh Taskfile.yml tests/test_secrets.bats
git commit -m "feat(secrets): add secrets:add-user task"
```

---

## Task 11: `secrets:set-user-password` and `secrets:rm-user`

**Files:**
- Modify: `scripts/secrets.sh`
- Modify: `Taskfile.yml`
- Modify: `tests/test_secrets.bats`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_secrets.bats`:

```bash
@test "secrets set-user-password: replaces hash for existing user" {
    old_hash="$(yq e '.caddy_users[] | select(.name == \"alice\") | .password_hash' "$LDS_CONFIG")"
    run bash -c "echo -e 'newpw\nnewpw' | $ROOT/scripts/secrets.sh set-user-password alice"
    [ "$status" -eq 0 ]
    new_hash="$(yq e '.caddy_users[] | select(.name == \"alice\") | .password_hash' "$LDS_CONFIG")"
    [[ "$new_hash" =~ ^\$2y\$14\$.{53}$ ]]
    [[ "$old_hash" != "$new_hash" ]]
}

@test "secrets set-user-password: refuses unknown user" {
    run bash -c "echo -e 'pw\npw' | $ROOT/scripts/secrets.sh set-user-password ghost"
    [ "$status" -ne 0 ]
    [[ "$output" == *"ghost"* ]]
}

@test "secrets rm-user: removes existing user" {
    run bash "$ROOT/scripts/secrets.sh" rm-user alice
    [ "$status" -eq 0 ]
    count="$(yq e '.caddy_users | map(select(.name == \"alice\")) | length' "$LDS_CONFIG")"
    [[ "$count" == "0" ]]
}

@test "secrets rm-user: refuses unknown user" {
    run bash "$ROOT/scripts/secrets.sh" rm-user ghost
    [ "$status" -ne 0 ]
    [[ "$output" == *"ghost"* ]]
}
```

- [ ] **Step 2: Run tests — verify failure**

```bash
bats tests/test_secrets.bats
```

- [ ] **Step 3: Add `cmd_set_user_password` and `cmd_rm_user`**

In `scripts/secrets.sh`, before `main()`:

```bash
cmd_set_user_password() {
    local name="${1:?usage: secrets.sh set-user-password <name>}"
    ensure_config

    local existing
    existing="$(yq e ".caddy_users[] | select(.name == \"$name\") | .name" "$CONFIG")"
    [[ -n "$existing" ]] || die "user $name not found"

    local pw hash
    pw="$(prompt_password "New password for $name")"
    hash="$(bcrypt_hash "$pw")"
    yq -i "(.caddy_users[] | select(.name == \"$name\") | .password_hash) = \"$hash\"" "$CONFIG"
    log "rotated password for $name"
}

cmd_rm_user() {
    local name="${1:?usage: secrets.sh rm-user <name>}"
    ensure_config

    local existing
    existing="$(yq e ".caddy_users[] | select(.name == \"$name\") | .name" "$CONFIG")"
    [[ -n "$existing" ]] || die "user $name not found"

    yq -i "del(.caddy_users[] | select(.name == \"$name\"))" "$CONFIG"
    log "removed user $name"
}
```

Update `main()`:

```bash
main() {
    local sub="${1:-}"; shift || true
    case "$sub" in
        add-user)            cmd_add_user "$@" ;;
        set-user-password)   cmd_set_user_password "$@" ;;
        rm-user)             cmd_rm_user "$@" ;;
        *) die "unknown subcommand: $sub" ;;
    esac
}
```

- [ ] **Step 4: Wire Taskfile entries**

Replace the two stubs:

```yaml
  "secrets:set-user-password":
    desc: Rotate password for an existing user
    cmd: bash scripts/secrets.sh set-user-password {{.CLI_ARGS}}

  "secrets:rm-user":
    desc: Remove a user
    cmd: bash scripts/secrets.sh rm-user {{.CLI_ARGS}}
```

- [ ] **Step 5: Run tests — verify pass**

```bash
bats tests/test_secrets.bats
```

Expected: 7 passing.

- [ ] **Step 6: Commit**

```bash
git add scripts/secrets.sh Taskfile.yml tests/test_secrets.bats
git commit -m "feat(secrets): add set-user-password and rm-user tasks"
```

---

## Task 12: `secrets:add-client`

**Files:**
- Modify: `scripts/secrets.sh`
- Modify: `Taskfile.yml`
- Modify: `tests/test_secrets.bats`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_secrets.bats`:

```bash
@test "secrets add-client: appends entry with random password and prints client invocation" {
    run bash "$ROOT/scripts/secrets.sh" add-client thermometer-7 9007
    [ "$status" -eq 0 ]
    name="$(yq e '.chisel_clients[] | select(.name == \"thermometer-7\") | .name' "$LDS_CONFIG")"
    port="$(yq e '.chisel_clients[] | select(.name == \"thermometer-7\") | .reverse_port' "$LDS_CONFIG")"
    pwd="$(yq e  '.chisel_clients[] | select(.name == \"thermometer-7\") | .password' "$LDS_CONFIG")"
    [[ "$name" == "thermometer-7" ]]
    [[ "$port" == "9007" ]]
    [[ "${#pwd}" -eq 32 ]]
    [[ "$output" == *"thermometer-7:$pwd"* ]]
    [[ "$output" == *"R:0.0.0.0:9007:localhost:80"* ]]
}

@test "secrets add-client: refuses duplicate name" {
    run bash "$ROOT/scripts/secrets.sh" add-client microscope-1 9099
    [ "$status" -ne 0 ]
    [[ "$output" == *"microscope-1"* ]]
}

@test "secrets add-client: refuses port already in use" {
    run bash "$ROOT/scripts/secrets.sh" add-client newdevice 9001
    [ "$status" -ne 0 ]
    [[ "$output" == *"9001"* ]]
}
```

- [ ] **Step 2: Run tests — verify failure**

```bash
bats tests/test_secrets.bats
```

- [ ] **Step 3: Add `cmd_add_client`**

In `scripts/secrets.sh`:

```bash
cmd_add_client() {
    local name="${1:?usage: secrets.sh add-client <name> <reverse_port>}"
    local port="${2:?usage: secrets.sh add-client <name> <reverse_port>}"
    ensure_config

    [[ "$port" =~ ^[0-9]+$ ]] || die "reverse_port must be numeric, got: $port"

    local existing_name existing_port
    existing_name="$(yq e ".chisel_clients[] | select(.name == \"$name\") | .name" "$CONFIG")"
    [[ -z "$existing_name" ]] || die "client $name already exists"
    existing_port="$(yq e ".chisel_clients[] | select(.reverse_port == $port) | .name" "$CONFIG")"
    [[ -z "$existing_port" ]] || die "reverse_port $port already in use by $existing_port"

    # Need vps.host for the printout; load via validate-only path.
    local host
    host="$(yq e '.vps.host' "$CONFIG")"
    [[ -n "$host" && "$host" != "null" ]] || die "vps.host missing in $CONFIG"

    local pw
    pw="$(gen_password)"
    yq -i ".chisel_clients += [{\"name\": \"$name\", \"reverse_port\": $port, \"password\": \"$pw\"}]" "$CONFIG"

    log "added client $name (port $port)"
    cat <<EOF

Run on the device:
  chisel client https://$host:$(yq e '.chisel.listen_port' "$CONFIG") \\
    $name:$pw \\
    R:0.0.0.0:$port:localhost:80

EOF
}
```

Update `main()`:

```bash
        add-client)          cmd_add_client "$@" ;;
```

- [ ] **Step 4: Wire Taskfile entry**

```yaml
  "secrets:add-client":
    desc: Add a chisel client (lab device); generates a random password
    cmd: bash scripts/secrets.sh add-client {{.CLI_ARGS}}
```

- [ ] **Step 5: Run tests — verify pass**

```bash
bats tests/test_secrets.bats
```

Expected: 10 passing.

- [ ] **Step 6: Commit**

```bash
git add scripts/secrets.sh Taskfile.yml tests/test_secrets.bats
git commit -m "feat(secrets): add secrets:add-client task"
```

---

## Task 13: `secrets:show-client` and `secrets:rm-client`

**Files:**
- Modify: `scripts/secrets.sh`
- Modify: `Taskfile.yml`
- Modify: `tests/test_secrets.bats`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_secrets.bats`:

```bash
@test "secrets show-client: re-prints invocation for existing client" {
    pwd="$(yq e '.chisel_clients[] | select(.name == \"microscope-1\") | .password' "$LDS_CONFIG")"
    run bash "$ROOT/scripts/secrets.sh" show-client microscope-1
    [ "$status" -eq 0 ]
    [[ "$output" == *"microscope-1:$pwd"* ]]
    [[ "$output" == *"R:0.0.0.0:9001:localhost:80"* ]]
}

@test "secrets show-client: refuses unknown client" {
    run bash "$ROOT/scripts/secrets.sh" show-client ghost
    [ "$status" -ne 0 ]
    [[ "$output" == *"ghost"* ]]
}

@test "secrets rm-client: removes existing client" {
    run bash "$ROOT/scripts/secrets.sh" rm-client microscope-1
    [ "$status" -eq 0 ]
    count="$(yq e '.chisel_clients | map(select(.name == \"microscope-1\")) | length' "$LDS_CONFIG")"
    [[ "$count" == "0" ]]
}

@test "secrets rm-client: refuses unknown client" {
    run bash "$ROOT/scripts/secrets.sh" rm-client ghost
    [ "$status" -ne 0 ]
    [[ "$output" == *"ghost"* ]]
}
```

- [ ] **Step 2: Run tests — verify failure**

```bash
bats tests/test_secrets.bats
```

- [ ] **Step 3: Add `cmd_show_client` and `cmd_rm_client`**

In `scripts/secrets.sh`:

```bash
cmd_show_client() {
    local name="${1:?usage: secrets.sh show-client <name>}"
    ensure_config

    local pw port host listen
    pw="$(yq e ".chisel_clients[] | select(.name == \"$name\") | .password" "$CONFIG")"
    port="$(yq e ".chisel_clients[] | select(.name == \"$name\") | .reverse_port" "$CONFIG")"
    [[ -n "$pw" && "$pw" != "null" ]] || die "client $name not found"

    host="$(yq e '.vps.host' "$CONFIG")"
    listen="$(yq e '.chisel.listen_port' "$CONFIG")"

    cat <<EOF
Run on the device:
  chisel client https://$host:$listen \\
    $name:$pw \\
    R:0.0.0.0:$port:localhost:80

EOF
}

cmd_rm_client() {
    local name="${1:?usage: secrets.sh rm-client <name>}"
    ensure_config

    local existing
    existing="$(yq e ".chisel_clients[] | select(.name == \"$name\") | .name" "$CONFIG")"
    [[ -n "$existing" ]] || die "client $name not found"

    yq -i "del(.chisel_clients[] | select(.name == \"$name\"))" "$CONFIG"
    log "removed client $name"
}
```

Update `main()`:

```bash
        show-client)         cmd_show_client "$@" ;;
        rm-client)           cmd_rm_client "$@" ;;
```

- [ ] **Step 4: Wire Taskfile entries**

```yaml
  "secrets:show-client":
    desc: Re-print chisel client invocation for an existing device
    cmd: bash scripts/secrets.sh show-client {{.CLI_ARGS}}

  "secrets:rm-client":
    desc: Remove a chisel client
    cmd: bash scripts/secrets.sh rm-client {{.CLI_ARGS}}
```

- [ ] **Step 5: Run tests — verify pass**

```bash
bats tests/test_secrets.bats
```

Expected: 14 passing.

- [ ] **Step 6: Commit**

```bash
git add scripts/secrets.sh Taskfile.yml tests/test_secrets.bats
git commit -m "feat(secrets): add show-client and rm-client tasks"
```

---

## Task 14: Fake-VPS Docker container for integration tests

**Files:**
- Create: `tests/fake_vps/Dockerfile`
- Create: `tests/fake_vps/start.sh`
- Create: `tests/fake_vps/README.md`

The fake VPS is an Ubuntu 24.04 container running OpenSSH with a `khamit` user (passwordless sudo, key-based SSH from the host). Provision/deploy tests `ssh` into it as if it were a real VPS.

- [ ] **Step 1: Write the Dockerfile**

`tests/fake_vps/Dockerfile`:

```dockerfile
FROM ubuntu:24.04

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        openssh-server sudo ca-certificates curl iproute2 && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash khamit && \
    echo 'khamit ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/khamit && \
    mkdir -p /home/khamit/.ssh && \
    chown khamit:khamit /home/khamit/.ssh && \
    chmod 700 /home/khamit/.ssh

# A test key is mounted at runtime (volume) so we don't bake credentials in.
RUN mkdir /var/run/sshd
EXPOSE 22

CMD ["/usr/sbin/sshd", "-D", "-e"]
```

- [ ] **Step 2: Write `tests/fake_vps/start.sh`**

```bash
#!/usr/bin/env bash
# Build, start, and configure the fake-VPS container. Idempotent.
# After this returns, you can `ssh -i tests/fake_vps/id_test -p 2222 khamit@127.0.0.1`.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAME="lds-fake-vps"
KEY="$HERE/id_test"

# 1. Generate a throwaway key if it doesn't exist.
if [[ ! -f "$KEY" ]]; then
    ssh-keygen -t ed25519 -N '' -f "$KEY" -C 'fake-vps-test'
fi

# 2. Build the image.
docker build -t "$NAME:latest" "$HERE"

# 3. Stop any prior instance.
docker rm -f "$NAME" >/dev/null 2>&1 || true

# 4. Start with /var/lib/docker as a tmpfs-ish volume so we can install Docker
#    inside it (provision.sh does this). We use --privileged for nested Docker.
docker run -d --name "$NAME" --privileged \
    -p 2222:22 -p 2080:80 -p 2443:443 -p 28080:8080 \
    -v "$KEY.pub:/home/khamit/.ssh/authorized_keys:ro" \
    "$NAME:latest"

# 5. Fix authorized_keys ownership and perms (read-only mount can be tricky;
#    copy it inside instead).
docker exec "$NAME" bash -c '
    cp /home/khamit/.ssh/authorized_keys /tmp/auth
    chown khamit:khamit /tmp/auth
    chmod 600 /tmp/auth
    mv /tmp/auth /home/khamit/.ssh/authorized_keys
'

# 6. Wait for sshd to be reachable.
for _ in {1..30}; do
    if ssh -i "$KEY" -p 2222 -o StrictHostKeyChecking=no -o BatchMode=yes \
           -o UserKnownHostsFile=/dev/null khamit@127.0.0.1 true 2>/dev/null; then
        echo "fake-vps ready on 127.0.0.1:2222"
        exit 0
    fi
    sleep 1
done
echo "fake-vps did not become reachable" >&2
exit 1
```

- [ ] **Step 3: Write the README**

`tests/fake_vps/README.md` (copy verbatim, including the inner triple-backtick fences):

````markdown
# Fake VPS

Ubuntu 24.04 container with sshd + khamit user, used for integration testing
provision.sh and deploy.sh without a real VPS. The integration test suite
auto-starts it; you can also run it manually:

```bash
bash tests/fake_vps/start.sh
ssh -i tests/fake_vps/id_test -p 2222 khamit@127.0.0.1
```

The throwaway SSH key (`id_test`, `id_test.pub`) is generated on first run
and gitignored.
````

- [ ] **Step 4: Add to `.gitignore`**

Append to `.gitignore`:

```
tests/fake_vps/id_test
tests/fake_vps/id_test.pub
```

- [ ] **Step 5: Smoke-test**

```bash
chmod +x tests/fake_vps/start.sh
bash tests/fake_vps/start.sh
ssh -i tests/fake_vps/id_test -p 2222 -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null khamit@127.0.0.1 'whoami; sudo -n whoami'
docker rm -f lds-fake-vps
```

Expected: prints `khamit\nroot`.

- [ ] **Step 6: Commit**

```bash
git add tests/fake_vps/Dockerfile tests/fake_vps/start.sh tests/fake_vps/README.md .gitignore
git commit -m "test: add fake-VPS container for integration tests"
```

---

## Task 15: `provision.sh`

**Files:**
- Create: `scripts/provision.sh`
- Create: `tests/test_provision.bats`
- Modify: `Taskfile.yml`

- [ ] **Step 1: Write the failing test**

`tests/test_provision.bats`:

```bash
#!/usr/bin/env bats

load helpers

# These tests boot the fake-VPS container and run provision.sh against it.
# They are slow (image build + Docker install). Mark with @tag if you want
# to skip in inner-loop runs.

setup_file() {
    bash "$ROOT/tests/fake_vps/start.sh"
}

teardown_file() {
    docker rm -f lds-fake-vps >/dev/null 2>&1 || true
}

setup() {
    setup_tmpdir
    cp "$ROOT/tests/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    # Point config at the fake VPS.
    yq -i ".vps.host = \"127.0.0.1\" | .vps.ssh_port = 2222" "$TMPDIR/config.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_SSH_KEY="$ROOT/tests/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
}
teardown() { teardown_tmpdir; }

@test "provision: installs docker, configures ufw, creates dirs" {
    run bash "$ROOT/scripts/provision.sh"
    [ "$status" -eq 0 ]
    # docker present
    docker exec lds-fake-vps bash -c 'command -v docker' >/dev/null
    # ufw enabled with the right ports
    docker exec lds-fake-vps ufw status | grep -q '22/tcp.*ALLOW'
    docker exec lds-fake-vps ufw status | grep -q '443/tcp.*ALLOW'
    docker exec lds-fake-vps ufw status | grep -q '8080/tcp.*ALLOW'
    # dirs exist with right ownership
    docker exec lds-fake-vps stat -c '%U' /srv/lab_devices_server | grep -q khamit
    docker exec lds-fake-vps stat -c '%U' /srv/jupyterlab/work     | grep -q khamit
}

@test "provision: re-running is idempotent (no errors)" {
    bash "$ROOT/scripts/provision.sh"
    run bash "$ROOT/scripts/provision.sh"
    [ "$status" -eq 0 ]
}
```

- [ ] **Step 2: Run tests — verify failure**

```bash
bats tests/test_provision.bats
```

(They'll fail because `provision.sh` doesn't exist yet.)

- [ ] **Step 3: Implement `scripts/provision.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=lib/config.sh
source "$SCRIPT_DIR/lib/config.sh"

CONFIG="${LDS_CONFIG:-$SCRIPT_DIR/../config.yaml}"

main() {
    load_config "$CONFIG"

    # Build SSH command (allow tests to inject key + opts).
    local ssh_base
    ssh_base="ssh -p $VPS_SSH_PORT"
    [[ -n "${LDS_SSH_KEY:-}" ]] && ssh_base="$ssh_base -i $LDS_SSH_KEY"
    [[ -n "${LDS_SSH_OPTS:-}" ]] && ssh_base="$ssh_base $LDS_SSH_OPTS"
    local target="$VPS_SSH_USER@$VPS_HOST"

    # 1. Reachability.
    log "checking SSH reachability..."
    $ssh_base -o BatchMode=yes -o ConnectTimeout=10 "$target" true \
        || die "cannot SSH to $target — check vps.host / vps.ssh_user / vps.ssh_port"

    # 2. Run remote provisioning script via stdin.
    log "running remote provisioning..."
    local remote_chisel_port="$CHISEL_LISTEN_PORT"
    local remote_root="$VPS_REMOTE_ROOT"
    local notebooks="$VPS_NOTEBOOKS_PATH"

    $ssh_base "$target" \
        "REMOTE_ROOT='$remote_root' NOTEBOOKS_PATH='$notebooks' CHISEL_PORT='$remote_chisel_port' bash -s" <<'REMOTE'
set -euo pipefail

log()  { printf '[remote] %s\n' "$*" >&2; }

# 1. Docker
if ! command -v docker >/dev/null 2>&1; then
    log "installing Docker..."
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER"
fi
docker --version

# 2. ufw
if ! command -v ufw >/dev/null 2>&1; then
    log "installing ufw..."
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ufw
fi
sudo ufw --force reset >/dev/null
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow "${CHISEL_PORT:?}"/tcp
sudo ufw --force enable

# 3. Directories. JupyterLab containers run as UID 1000 (jovyan).
sudo mkdir -p "$REMOTE_ROOT" "$REMOTE_ROOT/chisel" "$REMOTE_ROOT/caddy_data" "$NOTEBOOKS_PATH"
sudo chown -R "$USER:$USER" "$REMOTE_ROOT"
sudo chown -R 1000:100 "$NOTEBOOKS_PATH"
sudo chmod 775 "$NOTEBOOKS_PATH"
log "ok"
REMOTE

    log "✅ provisioned. next: task deploy"
}

main "$@"
```

- [ ] **Step 4: Wire into Taskfile**

```yaml
  provision:
    desc: First-time VPS setup (Docker, ufw, dirs). Idempotent.
    cmd: bash scripts/provision.sh
```

- [ ] **Step 5: Run integration tests**

```bash
bats tests/test_provision.bats
```

Expected: 2 passing. Each test takes 1–3 minutes due to Docker install.

- [ ] **Step 6: Commit**

```bash
git add scripts/provision.sh tests/test_provision.bats Taskfile.yml
git commit -m "feat(provision): add provision.sh with Docker, ufw, and dirs"
```

---

## Task 16: `deploy.sh`

**Files:**
- Create: `scripts/deploy.sh`
- Create: `tests/test_deploy.bats`
- Modify: `Taskfile.yml`

- [ ] **Step 1: Write the failing tests**

`tests/test_deploy.bats`:

```bash
#!/usr/bin/env bats

load helpers

setup_file() {
    bash "$ROOT/tests/fake_vps/start.sh"
}
teardown_file() {
    docker rm -f lds-fake-vps >/dev/null 2>&1 || true
}

setup() {
    setup_tmpdir
    cp "$ROOT/tests/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    yq -i ".vps.host = \"127.0.0.1\" | .vps.ssh_port = 2222" "$TMPDIR/config.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_SSH_KEY="$ROOT/tests/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    export LDS_SKIP_HEALTHCHECK=1   # tests don't need full TLS up; just deploy
    bash "$ROOT/scripts/provision.sh"
}
teardown() { teardown_tmpdir; }

@test "deploy: rsyncs templates and brings up containers" {
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -eq 0 ]
    docker exec lds-fake-vps test -f /srv/lab_devices_server/docker-compose.yml
    docker exec lds-fake-vps test -f /srv/lab_devices_server/Caddyfile
    docker exec lds-fake-vps test -f /srv/lab_devices_server/chisel/users.json
    # nested docker compose ps shows three services up
    docker exec lds-fake-vps bash -c '
        cd /srv/lab_devices_server && docker compose ps --status running --format "{{.Service}}"
    ' | sort | tr -d "\r" | grep -E "^(caddy|jupyter|chisel)$" | wc -l | grep -q 3
}

@test "deploy: rsync --delete preserves caddy_data" {
    bash "$ROOT/scripts/deploy.sh"
    docker exec lds-fake-vps bash -c 'echo testdata > /srv/lab_devices_server/caddy_data/marker'
    bash "$ROOT/scripts/deploy.sh"
    docker exec lds-fake-vps test -f /srv/lab_devices_server/caddy_data/marker
}

@test "deploy: rejects config with invalid hash before touching VPS" {
    cp "$ROOT/tests/fixtures/bad_hash_config.yaml" "$LDS_CONFIG"
    yq -i ".vps.host = \"127.0.0.1\" | .vps.ssh_port = 2222" "$LDS_CONFIG"
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -ne 0 ]
    [[ "$output" == *"bcrypt"* ]] || [[ "$output" == *"password_hash"* ]]
}
```

- [ ] **Step 2: Run tests — verify failure**

```bash
bats tests/test_deploy.bats
```

- [ ] **Step 3: Implement `scripts/deploy.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=lib/config.sh
source "$SCRIPT_DIR/lib/config.sh"
# shellcheck source=lib/render.sh
source "$SCRIPT_DIR/lib/render.sh"

CONFIG="${LDS_CONFIG:-$SCRIPT_DIR/../config.yaml}"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

main() {
    [[ -f "$CONFIG" ]] || die "config not found: $CONFIG (cp config.example.yaml config.yaml)"
    load_config "$CONFIG"

    # 1. Render to a staging dir.
    local stage
    stage="$(mktemp -d)"
    trap 'rm -rf "$stage"' EXIT

    log "rendering templates..."
    mkdir -p "$stage/chisel"
    render_compose     "$REPO_ROOT/compose/docker-compose.yml.tmpl" "$stage/docker-compose.yml"
    render_caddyfile   "$REPO_ROOT/compose/Caddyfile.tmpl"           "$stage/Caddyfile"
    render_chisel_users "$stage/chisel/users.json"

    # 2. Build SSH/rsync.
    local ssh_base rsync_e target
    ssh_base="ssh -p $VPS_SSH_PORT"
    [[ -n "${LDS_SSH_KEY:-}" ]] && ssh_base="$ssh_base -i $LDS_SSH_KEY"
    [[ -n "${LDS_SSH_OPTS:-}" ]] && ssh_base="$ssh_base $LDS_SSH_OPTS"
    rsync_e="$ssh_base"
    target="$VPS_SSH_USER@$VPS_HOST"

    # 3. Rsync. --delete with --exclude=caddy_data/ keeps issued certs.
    log "rsyncing to $target:$VPS_REMOTE_ROOT/ ..."
    rsync -az --delete --exclude='caddy_data/' \
        -e "$rsync_e" \
        "$stage/" "$target:$VPS_REMOTE_ROOT/"

    # 4. docker compose up.
    log "bringing up the stack..."
    $ssh_base "$target" "cd $VPS_REMOTE_ROOT && docker compose pull && docker compose up -d --remove-orphans"

    # 5. Health check (skippable for tests).
    if [[ "${LDS_SKIP_HEALTHCHECK:-}" != "1" ]]; then
        log "waiting for HTTPS to respond with 401..."
        local i status
        for ((i=0; i<60; i++)); do
            status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/" || true)"
            if [[ "$status" == "401" ]]; then
                log "✅ deployed at https://$VPS_HOST/"
                return 0
            fi
            sleep 1
        done
        warn "health check timed out (last status: $status). Check: task logs -- caddy"
        return 1
    fi
    log "✅ deployed (healthcheck skipped)"
}

main "$@"
```

- [ ] **Step 4: Wire into Taskfile**

```yaml
  deploy:
    desc: Render configs and bring up the stack on the VPS
    cmd: bash scripts/deploy.sh
```

- [ ] **Step 5: Run tests**

```bash
bats tests/test_deploy.bats
```

Expected: 3 passing.

- [ ] **Step 6: Commit**

```bash
git add scripts/deploy.sh tests/test_deploy.bats Taskfile.yml
git commit -m "feat(deploy): add deploy.sh with render + rsync + compose up"
```

---

## Task 17: Operations tasks (`logs`, `ps`, `ssh`, `restart`, `down`, `destroy`, `backup`)

**Files:**
- Create: `scripts/ops.sh`
- Modify: `Taskfile.yml`
- Test: `tests/test_ops.bats` (smoke-only; relies on fake-VPS post-deploy)

- [ ] **Step 1: Write the smoke tests**

`tests/test_ops.bats`:

```bash
#!/usr/bin/env bats

load helpers

setup_file() {
    bash "$ROOT/tests/fake_vps/start.sh"
}
teardown_file() {
    docker rm -f lds-fake-vps >/dev/null 2>&1 || true
}

setup() {
    setup_tmpdir
    cp "$ROOT/tests/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    yq -i ".vps.host = \"127.0.0.1\" | .vps.ssh_port = 2222" "$TMPDIR/config.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_SSH_KEY="$ROOT/tests/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    export LDS_SKIP_HEALTHCHECK=1
    bash "$ROOT/scripts/provision.sh"
    bash "$ROOT/scripts/deploy.sh"
}
teardown() { teardown_tmpdir; }

@test "ops ps: lists running services" {
    run bash "$ROOT/scripts/ops.sh" ps
    [ "$status" -eq 0 ]
    [[ "$output" == *"caddy"* ]]
    [[ "$output" == *"jupyter"* ]]
    [[ "$output" == *"chisel"* ]]
}

@test "ops logs: streams logs from a named service (--tail 5 --no-follow)" {
    run bash "$ROOT/scripts/ops.sh" logs jupyter
    [ "$status" -eq 0 ]
}

@test "ops restart: returns success" {
    run bash "$ROOT/scripts/ops.sh" restart
    [ "$status" -eq 0 ]
}

@test "ops down: stops the stack" {
    run bash "$ROOT/scripts/ops.sh" down
    [ "$status" -eq 0 ]
    docker exec lds-fake-vps bash -c '
        cd /srv/lab_devices_server && docker compose ps --status running --format "{{.Service}}"
    ' | grep -vE "^$" | wc -l | tr -d "[:space:]" | grep -q "^0$"
}

@test "ops backup: rsyncs notebooks to ./backups" {
    docker exec lds-fake-vps bash -c 'echo hello > /srv/jupyterlab/work/note.txt && chown 1000:100 /srv/jupyterlab/work/note.txt'
    cd "$TMPDIR"
    run bash "$ROOT/scripts/ops.sh" backup
    [ "$status" -eq 0 ]
    found="$(find "$TMPDIR/backups" -name 'note.txt' | head -1)"
    [[ -n "$found" ]]
    [[ "$(cat "$found")" == "hello" ]]
}
```

- [ ] **Step 2: Run tests — verify failure**

```bash
bats tests/test_ops.bats
```

- [ ] **Step 3: Implement `scripts/ops.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=lib/config.sh
source "$SCRIPT_DIR/lib/config.sh"

CONFIG="${LDS_CONFIG:-$REPO_ROOT/config.yaml}"

# Build SSH command honoring test env vars.
build_ssh() {
    local ssh_base="ssh -p $VPS_SSH_PORT"
    [[ -n "${LDS_SSH_KEY:-}" ]] && ssh_base="$ssh_base -i $LDS_SSH_KEY"
    [[ -n "${LDS_SSH_OPTS:-}" ]] && ssh_base="$ssh_base $LDS_SSH_OPTS"
    printf '%s' "$ssh_base"
}

remote_compose() {
    local args="$*"
    local ssh_base
    ssh_base="$(build_ssh)"
    $ssh_base "$VPS_SSH_USER@$VPS_HOST" "cd $VPS_REMOTE_ROOT && docker compose $args"
}

cmd_ps()       { load_config "$CONFIG"; remote_compose ps; }
cmd_restart()  { load_config "$CONFIG"; remote_compose restart; }
cmd_down()     { load_config "$CONFIG"; remote_compose down; }
cmd_destroy()  {
    load_config "$CONFIG"
    warn "this will remove containers AND volumes (caddy_data certs are preserved as a bind mount, but other state is gone)"
    remote_compose down -v
}

cmd_logs() {
    load_config "$CONFIG"
    local svc="${1:-}"
    if [[ -n "$svc" ]]; then
        remote_compose "logs --tail=200 -f $svc"
    else
        remote_compose "logs --tail=200 -f"
    fi
}

cmd_ssh() {
    load_config "$CONFIG"
    local ssh_base
    ssh_base="$(build_ssh)"
    exec $ssh_base "$VPS_SSH_USER@$VPS_HOST"
}

cmd_backup() {
    load_config "$CONFIG"
    local ssh_base ts dest
    ssh_base="$(build_ssh)"
    ts="$(date +%Y%m%d-%H%M%S)"
    dest="./backups/notebooks-$ts"
    mkdir -p "$dest"
    log "rsyncing $VPS_NOTEBOOKS_PATH/ -> $dest/"
    # Use sudo on the remote because /srv/jupyterlab/work is owned by uid 1000.
    rsync -az --rsync-path='sudo rsync' -e "$ssh_base" \
        "$VPS_SSH_USER@$VPS_HOST:$VPS_NOTEBOOKS_PATH/" "$dest/"
    log "✅ backed up to $dest/"
}

main() {
    local sub="${1:-}"; shift || true
    case "$sub" in
        ps)        cmd_ps ;;
        logs)      cmd_logs "$@" ;;
        ssh)       cmd_ssh ;;
        restart)   cmd_restart ;;
        down)      cmd_down ;;
        destroy)   cmd_destroy ;;
        backup)    cmd_backup ;;
        *) die "unknown subcommand: $sub" ;;
    esac
}

main "$@"
```

- [ ] **Step 4: Wire into Taskfile**

Replace the seven stubs:

```yaml
  ps:       { desc: "docker compose ps on the VPS",                 cmd: "bash scripts/ops.sh ps" }
  logs:     { desc: "Stream logs (optionally for a single service)", cmd: "bash scripts/ops.sh logs {{.CLI_ARGS}}" }
  ssh:      { desc: "Open an interactive SSH session to the VPS",   cmd: "bash scripts/ops.sh ssh" }
  restart:  { desc: "docker compose restart",                       cmd: "bash scripts/ops.sh restart" }
  down:     { desc: "docker compose down",                          cmd: "bash scripts/ops.sh down" }
  destroy:  { desc: "docker compose down -v (DANGEROUS)",            cmd: "bash scripts/ops.sh destroy" }
  backup:   { desc: "rsync notebooks to ./backups/notebooks-<ts>/", cmd: "bash scripts/ops.sh backup" }
```

- [ ] **Step 5: Run tests**

```bash
bats tests/test_ops.bats
```

Expected: 5 passing.

- [ ] **Step 6: Smoke-test from the Taskfile**

```bash
task --list
```

Expected: every task has a real description; no remaining `(stub)` entries.

- [ ] **Step 7: Commit**

```bash
git add scripts/ops.sh tests/test_ops.bats Taskfile.yml
git commit -m "feat(ops): add ps/logs/ssh/restart/down/destroy/backup tasks"
```

---

## Task 18: End-to-end smoke against the fake VPS, doc README quick-start, final commit

**Files:**
- Modify: `README.md` (only if any quick-start command needs correction after running it end-to-end)
- Modify: `Taskfile.yml` (add a `test` task)

- [ ] **Step 1: Add a `test` task**

```yaml
  test:
    desc: Run all bats tests (requires bats-core; integration tests need Docker)
    cmd: bats tests/
```

- [ ] **Step 2: Run the full test suite**

```bash
task test
```

Expected: every test passes. Total runtime ~3–6 minutes (most spent in provision-related Docker-install steps).

- [ ] **Step 3: Run the documented quick-start end-to-end against the fake VPS**

```bash
bash tests/fake_vps/start.sh

# Simulate operator workflow.
cp config.example.yaml config.yaml
yq -i '.vps.host = "127.0.0.1" | .vps.ssh_port = 2222' config.yaml

export LDS_SSH_KEY=tests/fake_vps/id_test
export LDS_SSH_OPTS='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
export LDS_SKIP_HEALTHCHECK=1

echo -e 'hunter2\nhunter2' | task secrets:add-user -- alice
task secrets:add-client -- microscope-1 9001
task provision
task deploy
task ps
task ssh   # interactive — exit out
task down

# Cleanup
docker rm -f lds-fake-vps
rm config.yaml
```

Expected: all tasks succeed; `task ps` shows three running services; `task secrets:add-client` prints the chisel-client invocation.

- [ ] **Step 4: Update README if anything in the quick-start was inaccurate**

If any command differs from what's in `README.md`, fix the README to match. Otherwise skip.

- [ ] **Step 5: Final commit**

```bash
git add Taskfile.yml README.md
git commit -m "test: add task test target; verified e2e against fake VPS"
```

---

## Self-review — coverage map

Spec section → tasks that implement it:

- **Repository layout** → Task 1, Task 2, Task 4
- **Config schema (committed example, gitignored real)** → Task 1 (`.gitignore`), Task 2
- **Authentication model — JupyterLab / Caddy basic auth** → Task 7 (Caddyfile template), Task 9 (bcrypt), Task 10–11 (user secrets)
- **Authentication model — Chisel per-client routes** → Task 8 (chisel users.json), Task 12–13 (client secrets)
- **TLS — short-lived IP cert via ACME with internal-CA fallback** → Task 7 (Caddyfile template's `issuer acme { profile shortlived } / issuer internal`)
- **Container topology + port table** → Task 6 (compose template; jupyter has no `ports:`, chisel publishes only `listen_port`, reverse_ports never published)
- **Provisioning flow** → Task 14 (fake VPS), Task 15 (`provision.sh`)
- **Deploy flow including `--exclude=caddy_data/`** → Task 16 (`deploy.sh`, with explicit test in Task 16 step 1 that caddy_data marker survives a redeploy)
- **Validation rules (required fields, bcrypt hash format, duplicate ports)** → Task 5 (`config.sh::validate_config`) with fixtures
- **Failure modes (validation pre-flight, ACME fallback, rsync mid-deploy)** → Task 5 + Task 7 + Task 16
- **Taskfile surface (lifecycle, secrets, ops)** → Tasks 4, 10–13, 15, 16, 17
- **Backups (local-only, timestamped)** → Task 17 (`cmd_backup`)
- **Image pinning** → Task 2 (config.example.yaml ships pinned tags)
- **ufw rules (22/80/443/listen_port)** → Task 15

No spec sections without coverage.
