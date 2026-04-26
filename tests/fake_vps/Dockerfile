FROM ubuntu:24.04

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        openssh-server sudo ca-certificates curl iproute2 && \
    rm -rf /var/lib/apt/lists/*

# Ubuntu 24.04's base image ships with a default `ubuntu` user at UID 1000.
# A real production VPS provisioned by the operator will have khamit at UID 1000.
# Mirror that here so jupyter's jovyan (UID 1000 inside the container) matches
# the bind-mount owner.
RUN userdel -r ubuntu 2>/dev/null || true && \
    useradd -m -u 1000 -s /bin/bash khamit && \
    echo 'khamit ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/khamit && \
    mkdir -p /home/khamit/.ssh && \
    chown khamit:khamit /home/khamit/.ssh && \
    chmod 700 /home/khamit/.ssh

# A test key is mounted at runtime (volume) so we don't bake credentials in.
RUN mkdir /var/run/sshd
EXPOSE 22

CMD ["/usr/sbin/sshd", "-D", "-e"]
