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
