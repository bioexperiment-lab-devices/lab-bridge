# Registering a new lab

One lab is one SerialHop installation on one lab PC, talking to one or more bench instruments. Registering a lab means minting a per-lab chisel credential on the VPS, handing it to the lab's operator out-of-band, and verifying that the lab dialed in once the operator pastes the credential into `SerialHop_config.yaml`.

## Issuing credentials

Run this on your laptop:

```bash title="laptop"
task secrets:add-client -- <lab-name> <reverse-port>
```

The two arguments (semantics mirror `scripts/secrets.sh:126-128`):

- **`<lab-name>`** — a short, stable identifier for the lab. It becomes the chisel `user` and the lab name researchers pass to `LabDevicesClient(user=…)` in notebooks. Lowercase, no spaces; underscores are fine. Examples: `khamit_desktop`, `lab1_pc`, `microscope_1`.
- **`<reverse-port>`** — the port on the VPS chisel server where this lab's local HTTP API gets published into `labnet`, so JupyterLab and Flasher can reach it by container DNS as `chisel:<reverse-port>`. Pick the next unused port in your numbering scheme (start at 9001 and walk up). The task validates against existing entries in `chisel_clients` in `config.yaml` and refuses to clobber a name or port that's already in use.

A successful run prints the chisel client invocation, with a freshly generated random password:

```text
added client lab1_pc (port 9001)

Run on the device:
  chisel client https://<vps-host>:<chisel-listen-port> \
    lab1_pc:<random-password> \
    R:0.0.0.0:9001:localhost:80
```

That is the `chisel client …` command the operator runs on the lab PC — or, more commonly, the values the operator pastes into `SerialHop_config.yaml` so the agent reconnects automatically on every boot.

## Handing creds to the operator

The printout above contains a long-lived password. Give it to the operator out-of-band — 1Password share, Signal, encrypted email — not over Slack DMs or plaintext email. They paste the values (host, port, lab name, password) into `SerialHop_config.yaml` on the lab PC; the operator-side walkthrough is at [setup the lab PC](/docs/operator/setup-lab-pc).

If you ever need to re-print the printout for an existing lab (e.g. the operator lost it before pasting), use `task secrets:show-client -- <lab-name>` — it pulls the password back out of `config.yaml` and re-prints the same block. Note: `secrets:show-client` re-prints the same long-lived password from `config.yaml`. Use it only if the operator never received the credential. If it was received and may have leaked, rotate instead — see [Rotating credentials](#rotating-credentials).

## Verifying the lab is online

After the operator starts SerialHop, check from your end:

- Visit `https://<vps-host>/`. The new lab should appear in the "Registered labs" panel. The pill next to its name turns **ONLINE** once the chisel session is up.
- Open `/grafana/d/lab-bridge-client-logs/lab-client-logs` and filter by the new lab name. You should see a live log stream — at minimum the SerialHop startup messages, version banner, and the first chisel session handshake.
- From a notebook on the shared JupyterLab: `LabDevicesClient.list_active_users()` should include the new lab name in its return value.

## Rotating credentials

`task secrets:add-client` refuses to clobber an existing entry (`scripts/secrets.sh:134-135`). To rotate a lab's password:

1. Remove the lab's entry — easiest path: `task secrets:rm-client -- <lab-name>`. This deletes the entry from `chisel_clients` in `config.yaml`. (You can also delete the entry from `config.yaml` by hand if you'd rather.)
2. Re-mint: `task secrets:add-client -- <lab-name> <reverse-port>` with the same arguments. A fresh random password is generated.
3. `task deploy` to push the new allowlist into the chisel container.
4. Hand the new printout to the operator.

Coordinate with the operator before rotating — the lab goes offline at step 3 and stays offline until the new password reaches `SerialHop_config.yaml` and SerialHop restarts.

## Removing a lab

To retire a lab permanently:

```bash title="laptop"
task secrets:rm-client -- <lab-name>
task deploy
```

`task secrets:rm-client` deletes the entry from the `chisel_clients` array in `config.yaml`. `task deploy` re-renders the allowlist — `render_chisel_users` (`scripts/lib/render.sh:97`) emits a fresh `chisel/users.json` without the lab — and rsyncs it to the VPS. The lab can no longer authenticate against the chisel server after the restart.
