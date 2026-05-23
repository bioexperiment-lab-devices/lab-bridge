# Users and groups

lab-bridge users live in Authelia's flat file backend at `compose/authelia/users_database.yml`. All operations go through `task users:*` on your laptop — never hand-edit the file. Group membership controls what each user can reach; the full route-to-group mapping is in [authentication and authorization](/docs/architecture/auth).

## Groups

Only two groups are meaningful in this install:

- **`researchers`** — JupyterLab (`/jupyter/*`) and Grafana with the Viewer role. Cannot reach Flasher.
- **`admins`** — everything `researchers` can reach, plus Grafana with the Admin role and Flasher (`/flash/*`).

Users with no group can sign in but every gated route rejects them, so they bounce back to the login page. Add new users to at least one of the two.

## Adding a researcher

```bash title="laptop"
task users:add -- jane researchers
task deploy                                 # rsyncs the users file to the VPS
```

`task users:add` prompts twice for a password, writes the argon2id hash into `compose/authelia/users_database.yml`, and prints the resulting record. `task deploy` rsyncs the file to the VPS and restarts Authelia. Hand the password to Jane out-of-band.

## Adding an admin

```bash title="laptop"
task users:add -- jane admins
task deploy
```

Same flow, different group. Jane now has Flasher access and the Grafana Admin role on her next sign-in.

## Other operations

```bash title="laptop"
task users:list                                  # show all users
task users:set-password -- jane                  # rotate jane's password
task users:set-groups -- jane admins,researchers # change membership
task users:rm -- jane                            # remove jane (laptop file; deploy to apply)
```

`task users:set-groups` replaces the user's group list — it does not append. Pass the complete intended list (`admins,researchers` not just `admins`) if you want them in both. Every mutation requires `task deploy` to land on the VPS.

## Forgotten password

There is no self-service password reset — no SMTP is configured. An admin runs `task users:set-password -- <name>` on their laptop, then `task deploy`, then hands the new password to the user out-of-band.

## Lost bootstrap admin

If you locked yourself out of every admin account, recover directly on the VPS, then resync.

1. SSH to the VPS (`task ssh`).
2. Generate an argon2id hash for the new password:

   ```bash title="vps"
   docker run --rm authelia/authelia:4.38.10 \
     authelia crypto hash generate argon2 --password 'newpassword' --no-confirm
   ```

3. Paste the hash into `/srv/lab-bridge/authelia/users_database.yml` under the locked user's `password:` field.
4. Restart Authelia: `docker compose -f /srv/lab-bridge/docker-compose.yml restart authelia`.

You can now sign in with the new password.

> [!WARNING]
> Direct edits on the VPS are temporary — the next `task deploy` rsyncs `compose/authelia/users_database.yml` from your laptop and overwrites the file. As soon as access is restored, run `task users:set-password -- <name>` on the laptop to sync the laptop copy, then `task deploy` to make the change permanent.
