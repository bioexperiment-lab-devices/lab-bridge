"""Shared pytest configuration for unit tests."""

import respx

# respx 0.21 + httpx 0.28 incompatibility: the default HTTPCoreMocker backend
# passes bytes method from httpcore, which fails Method pattern matching.
# Switch the global mock to the httpx transport backend to avoid this.
respx.mock._using = "httpx"
