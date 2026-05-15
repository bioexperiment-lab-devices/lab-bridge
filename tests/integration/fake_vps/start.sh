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

# 2. Build the image (--load ensures it lands in the local daemon when buildx is active).
docker build --load -t "$NAME:latest" "$HERE"

# 3. Stop any prior instance.
docker rm -f "$NAME" >/dev/null 2>&1 || true

# 4. Start with --privileged for nested Docker (provision.sh installs Docker inside).
docker run -d --name "$NAME" --privileged \
    -p 2222:22 -p 2080:80 -p 2443:443 -p 28080:8080 \
    "$NAME:latest"

# 5. Copy the public key in and set correct ownership/perms.
docker cp "$KEY.pub" "$NAME:/tmp/authorized_keys"
docker exec "$NAME" bash -c '
    cp /tmp/authorized_keys /home/khamit/.ssh/authorized_keys
    chown khamit:khamit /home/khamit/.ssh/authorized_keys
    chmod 600 /home/khamit/.ssh/authorized_keys
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
