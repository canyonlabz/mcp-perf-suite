# MS Teams MCP Troubleshooting

This guide addresses common issues encountered when using the `msteams-mcp` server for performance test notifications, search, and channel operations.

---

## Substrate Token Missing After Restart (`No valid Substrate token`)

**Symptom:**
`teams_send_message` fails with `INVALID_INPUT: No valid Substrate token — interactive login required` even though `teams_status` shows skype/auth tokens as healthy.

**Cause:**
The Substrate token (required for mention email resolution via `teams_search_people`) has a shorter effective lifetime than the session cookies. After a Cursor restart or overnight session, SSO restores the session from cached cookies but does not re-extract the Substrate token from browser `localStorage`.

**Fix:**
Clear the contents of the `~/.teams-mcp-server/` directory and restart Cursor. The next `teams_login(force=True)` call will open a real browser window, perform a full login, and capture all tokens including the Substrate token.

```bash
rm -rf ~/.teams-mcp-server/*
```

After clearing, restart Cursor and call `teams_login` — log into Teams in the browser when the window opens.

---

## `force=True` Does Not Open Browser When Session Cookies Are Valid

**Symptom:**
`teams_login(force=True)` returns `method: "sso"` and does not open a browser window, even when called explicitly to refresh tokens.

**Cause:**
The `force=True` flag bypasses the session expiry check but still falls back to SSO if valid session cookies exist in the browser profile (`~/.teams-mcp-server/.user-data/`). Deleting only `session-state.json` or `token-cache.json` is insufficient — Playwright restores from the browser profile directory.

**Fix:**
Delete all contents of `~/.teams-mcp-server/` as described above, then restart Cursor.

---

## Config Changes Not Picked Up (Requires Cursor Restart)

**Symptom:**
Changes to `config.mac.yaml` or `config.windows.yaml` (e.g. adding a `mentions:` list, adding a new chat target, changing a `conversation_id`) are not reflected by the MCP server.

**Cause:**
The MCP server loads config at module import time. The config is cached in memory for the lifetime of the process. Cursor must be restarted to reload it.

**Fix:**
Restart Cursor after any change to your config YAML file. There is no hot-reload mechanism.

---

## @mentions Rendering as Plain Text (No Blue Highlight)

**Symptom:**
Mentioned names appear in the Teams message as plain text without the blue highlight, and recipients do not receive a notification ping.

**Cause:**
The chatsvc API requires a specific HTML structure (`<readonly><span>` with schema.skype.com attributes) and a `properties.mentions` JSON-encoded string in the POST body. Using `<at>` tags or placing mentions at the top level of the body does not work.

**Fix:**
This was fixed in the April 20, 2026 update. If you are still seeing this, ensure you are running the latest version of `services/teams_api.py` with the `build_mention_tags()` function that uses `<readonly>` + `<span>` HTML and `properties.mentions`.

---

## Template Not Being Used (Config Template Overriding Caller)

**Symptom:**
Calling `teams_send_message(target="my-channel", template="notification-start-test.md")` uses the config-defined template for that channel instead of the explicitly passed one.

**Cause:**
In versions before April 21, 2026, the config-level `template:` entry for a channel had highest priority, overriding the caller's `template` parameter.

**Fix:**
This was fixed in the April 21, 2026 update. The resolution order is now:

1. **Caller-specified template** — highest priority
2. **Config channel template** — fallback when caller doesn't specify
3. **`default-{name}`** — built-in fallback

Ensure you are running the latest version of `services/template_manager.py`.

---

*Last updated: April 21, 2026*
