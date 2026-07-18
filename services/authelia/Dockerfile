# Re-publishes upstream authelia/authelia under our GHCR namespace so the
# image carries the same Sigstore attestation chain as siteapp / flasher / caddy.
# The tag (root VERSION, release-please-managed) is what gets bumped; the base
# pin lives in compose/images.yaml and is Renovate-managed.
ARG AUTHELIA_VERSION=4.38.10
FROM authelia/authelia:${AUTHELIA_VERSION}
