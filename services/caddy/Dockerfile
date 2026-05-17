# syntax=docker/dockerfile:1.7
ARG CADDY_VERSION=2.8.4
# REPLACE_RESPONSE_VERSION is a Go module pseudo-version because
# caddyserver/replace-response has no tagged releases — we pin a specific
# commit. When bumping, also confirm CADDY_VERSION compatibility: the
# plugin's go.mod (at the pinned commit) declares the minimum Caddy
# version it supports, and xcaddy will fail if CADDY_VERSION is older.
# As of 2025-06 the plugin's master requires Caddy 2.9.x, so we pin the
# last commit compatible with the 2.8 line (3865845790a7, 2024-12-11).
# Bump candidate commits at https://github.com/caddyserver/replace-response/commits/master
# — but check that commit's go.mod against CADDY_VERSION first.
ARG REPLACE_RESPONSE_VERSION=v0.0.0-20241211194404-3865845790a7

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
