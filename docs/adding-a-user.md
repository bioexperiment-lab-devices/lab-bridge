# Adding a user

Lab-bridge uses Authelia for authentication. Users live in
`compose/authelia/users_database.yml`. Managed via `task users:*`.

## First-time bootstrap

1. Generate Authelia's runtime secrets (once per VPS):
   ```bash
   task secrets:bootstrap-authelia
   ```
2. Add the bootstrap admin:
   ```bash
   task users:add -- you admins
   # Prompts for password.
   ```
3. Deploy:
   ```bash
   task deploy
   ```

## Adding a researcher

```bash
task users:add -- jane researchers
task deploy
```

`researchers` can sign in to JupyterLab and view Grafana dashboards.

## Adding an admin

```bash
task users:add -- jane admins
task deploy
```

`admins` get full access — JupyterLab, Grafana (as Grafana `Admin` role),
and Flasher.

## Other operations

```bash
task users:list                                  # show all users
task users:set-password -- jane                  # rotate jane's password
task users:set-groups -- jane admins,researchers # change membership
task users:rm -- jane                            # remove jane (immediate effect on next request)
```

## Forgotten password recovery

There is no self-service reset (no SMTP). An admin runs:

```bash
task users:set-password -- jane
```

…and tells Jane the new password out-of-band.

## Loss of bootstrap admin

If every admin has lost their password:

1. SSH to the VPS.
2. Generate an argon2id hash:
   ```bash
   docker run --rm authelia/authelia:4.38.10 \
     authelia crypto hash generate argon2 --password 'newpassword' --no-confirm
   ```
3. Paste the hash into `/srv/lab-bridge/authelia/users_database.yml` under the relevant user's `password:` field.
4. `docker compose restart authelia`.
