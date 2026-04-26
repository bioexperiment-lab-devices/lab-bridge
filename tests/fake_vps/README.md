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
