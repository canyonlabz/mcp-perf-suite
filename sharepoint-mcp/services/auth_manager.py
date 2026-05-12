"""
Authentication orchestration for SharePoint MCP.

Three-layer token resolution:
  1. Token cache — fast path, no I/O
  2. Session state — re-extract tokens from encrypted Playwright state
  3. Browser login — launch Playwright, attempt SSO, fall back to manual login

All entry points are async and guarded by an asyncio.Lock to prevent
concurrent browser launches or token refresh races.
"""

# Implementation follows in subsequent tasks
