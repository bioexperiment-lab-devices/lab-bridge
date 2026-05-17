# syntax=docker/dockerfile:1.7
# CADDY_VERSION must be ≥ 2.10 because compose/Caddyfile.tmpl uses the
# `profile shortlived` ACME issuer property, which was added in Caddy 2.10.
ARG CADDY_VERSION=2.11.3
# REPLACE_RESPONSE_VERSION is a Go module pseudo-version because
# caddyserver/replace-response has no tagged releases — we pin a specific
# commit. When bumping, also confirm CADDY_VERSION compatibility: the
# plugin's go.mod (at the pinned commit) declares the minimum Caddy
# version it supports, and xcaddy will fail if CADDY_VERSION is older.
# The June 2025 commit below requires Caddy ≥ 2.9.1 and is compatible with
# 2.11.x. Bump candidates at https://github.com/caddyserver/replace-response/commits/master
# — but check that commit's go.mod against CADDY_VERSION first.
ARG REPLACE_RESPONSE_VERSION=v0.0.0-20250618171559-80962887e4c6

FROM caddy:${CADDY_VERSION}-builder AS builder
ARG REPLACE_RESPONSE_VERSION
RUN xcaddy build \
    --with github.com/caddyserver/replace-response@${REPLACE_RESPONSE_VERSION}

FROM caddy:${CADDY_VERSION}
COPY --from=builder /usr/bin/caddy /usr/bin/caddy

ARG LAB_BRIDGE_VERSION=dev
ARG LAB_BRIDGE_GIT_SHA=unknown
ENV LAB_BRIDGE_VERSION=$LAB_BRIDGE_VERSION \
    LAB_BRIDGE_GIT_SHA=$LAB_BRIDGE_GIT_SHA
