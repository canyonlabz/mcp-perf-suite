---
name: jmeter-entraid-debugging
description: >-
  Diagnose and fix JMeter script failures in Microsoft Entra ID (Azure AD)
  authentication flows including OAuth2/OIDC authorize, WS-Federation, OpenAM,
  and Kerberos SSO. Use when debugging JMeter scripts that interact with
  login.microsoftonline.com, EntraID, Entra ID, Azure AD, WS-Federation, wsfed,
  OpenAM, BssoInterrupt, MSAL, ConvergedSignIn, GetCredentialType, flowToken,
  ESTSWCTXFLOWTOKEN, or any Microsoft identity platform login flow.
disable-model-invocation: true
---

# EntraID Authentication Flow Debugging

This skill provides domain-specific knowledge for debugging JMeter scripts that
interact with Microsoft Entra ID (formerly Azure AD) authentication flows. It is
a companion to the `jmeter-debugging` skill, which provides the iterative debug
workflow (smoke test, triage, fix, repeat). This skill tells you **what to look
for** and **how to fix it** when the auth flow is EntraID.

## When to Use This Skill

- JMeter errors occur on samplers targeting `login.microsoftonline.com`
- Log analysis reveals `$Config`, `sFT`, `sCtx`, `wresult`, or `BssoInterrupt`
- The auth flow involves WS-Federation, OpenAM, or Kerberos Seamless SSO
- The user mentions EntraID, Azure AD, or Microsoft identity login issues
- The correlation engine detected EntraID flow markers in the network capture

**Workflow integration:** Use the `jmeter-debugging` skill for the debug loop
mechanics (Steps 1-10). Consult this skill during **Step 5 (Triage)** and
**Step 7 (Diagnose)** when the failing samplers are part of an EntraID flow.

---

## Flow Recognition

The agent is dealing with an EntraID flow when ANY of these are present:

| Indicator | Where to Look |
|-----------|---------------|
| `login.microsoftonline.com` | Request URLs |
| `$Config=` JavaScript object | HTML response body |
| `PageID=ConvergedSignIn` | HTML response body |
| `PageID=BssoInterrupt` | HTML response body |
| `wresult`, `wctx` hidden inputs | HTML form body |
| `response_mode=fragment` | `/oauth2/v2.0/authorize` URL params |
| `GetCredentialType` | POST URL path |
| `/openam/WSFederationServlet` | Request URL path |

---

## Diagnosis Patterns

These patterns are ordered by the typical sequence in which they appear during
an EntraID login flow. Each pattern includes the symptom, root cause, and fix.

### 1. response_mode=fragment Incompatibility

**Symptom:** After the authorize redirect, JMeter receives a 302 to a callback
URL with `#code=...` in the fragment. JMeter cannot read URL fragments -- the
`code` value is lost.

**Root cause:** The application uses MSAL.js with `response_mode=fragment`
(default for SPAs). Fragments are handled client-side by JavaScript, which
JMeter does not execute.

**Fix:**
- Change the `response_mode` User Defined Variable from `fragment` to `query`
- Disable "Follow Redirects" and "Auto Redirects" on the authorize sampler
- Add a `regex_extractor` on the authorize sampler: `[?&]code=([^&#\s]+)`

### 2. BssoInterrupt / Seamless SSO Page

**Symptom:** The authorize request returns HTTP 200 with an HTML page instead
of a 302 redirect. The page contains `PageID=BssoInterrupt` and JavaScript
that attempts Kerberos Integrated Windows Authentication.

**Root cause:** EntraID detects a domain-joined device and returns a page that
triggers IWA via JavaScript. JMeter cannot execute this JavaScript.

**Fix:**
- Add a follow-up GET sampler to the same authorize URL with `&sso_reload=True`
  appended as a query parameter
- This tells EntraID to skip the IWA attempt and return the sign-in page

### 3. Missing $Config Field Extractions

**Symptom:** Subsequent POST requests fail with 400/403 because `flowToken`,
`sCtx`, `canary`, or `sessionId` values are missing or stale.

**Root cause:** After `sso_reload`, EntraID returns the `ConvergedSignIn` page
containing a `$Config` JavaScript object with these dynamic values. They must
be extracted from the HTML response body.

**Fix:** Add `regex_extractor`s on the sign-in page sampler:
- `flowToken_1`: `sFT":"(.*?)"`
- `sCtx_1`: `"sCtx":"(.*?)"`
- `Canary`: `"canary":"(.*?)"`
- `SessionID`: `sessionId":"(.*?)"`

### 4. GetCredentialType Flow

**Symptom:** After submitting credentials, the flow fails because
`FederationRedirectUrl` or `estsrequest` values are not available for the
next redirect.

**Root cause:** EntraID's `/common/GetCredentialType` API returns a JSON
response indicating how to authenticate the user. For federated users, it
contains `FederationRedirectUrl` with an embedded `estsrequest` parameter.

**Fix:**
- Ensure the POST to `/common/GetCredentialType` includes: `username`,
  `flowToken` (from pattern 3), and `originalRequest` (sCtx from pattern 3)
- Add extractors on the GetCredentialType response:
  - `federationRedirectUrl`: `FederationRedirectUrl":"(.*?)"`
  - `estsrequest`: `estsrequest%3d(.*?)"`

### 5. OpenAM WS-Federation Chain

**Symptom:** After the federation redirect, JMeter hits OpenAM endpoints that
return `authId` in JSON responses. Subsequent authenticate calls fail without
the correct `authId`, `nonce`, or `cdssoToken`.

**Root cause:** The federated IdP uses OpenAM/ForgeRock with a multi-step
authenticate flow. Each step returns a new `authId` that must be passed to
the next step.

**Fix:** Add extractors on each OpenAM `/json/authenticate` response:
- `AuthId`: `"authId":"(.*?)"` (extracted on each authenticate step)
- `nonce`: `"nonce":"(.*?)==` (note the `==` suffix for base64 padding)
- `cdssoToken`: `"cdssoToken":"(.*?)"`

Multiple authenticate calls may occur (username callback, password callback).
Each returns a new `authId` -- extract and use the latest one.

### 6. WS-Fed Form Post with Large wresult

**Symptom:** The WS-Federation return page submits a form back to EntraID with
`wresult` (SAML token XML), `wctx`, and `wa` hidden fields. Regex extraction
fails on `wresult` because the value is very large (multi-KB XML).

**Root cause:** The `wresult` value is a full SAML token wrapped in XML. Regex
extractors can fail or become very slow on values this large.

**Fix:**
- Use `boundary_extractor` (not regex) for `wresult`:
  - Left boundary: `<input type="hidden" name="wresult" value="`
  - Right boundary: `">`
- Use `regex_extractor` for `wctx`: `name="wctx" value="([^"]+)"`
- Extract tenant GUID from form action URL: `com&#x2f;(.*?)&#x2f;wsfed"`

### 7. ESTSWCTXFLOWTOKEN Cookie Injection

**Symptom:** The WS-Fed form POST to EntraID returns an error page or redirect
loop because expected cookies are missing.

**Root cause:** EntraID expects two cookies when processing the WS-Fed form
submission: `ESTSWCTXFLOWTOKEN` (set to the current flowToken) and `AADSSO`
(set to `NA|NoExtension`). These are normally set by JavaScript on the
previous page, which JMeter does not execute.

**Fix:** Add `entra_wsfed_cookie_preprocessor` to the WS-Fed form POST sampler:
```
add_jmeter_component(
  component_type   = "entra_wsfed_cookie_preprocessor",
  parent_node_id   = {wsfed_post_sampler_node_id},
  component_config = {
    "flow_token_var": "flowToken_2",
    "domain":         "login.microsoftonline.com"
  }
)
```

### 8. MSAL oauth_state Format

**Symptom:** The authorize callback fails validation because the `state`
parameter format is incorrect.

**Root cause:** MSAL.js generates `state` as a base64url-encoded JSON object
`{id: UUID, meta: {interactionType: "redirect"}}`. EntraID validates this
format. A plain UUID will not work.

**Fix:** Add `entra_state_preprocessor` to the authorize sampler:
```
add_jmeter_component(
  component_type   = "entra_state_preprocessor",
  parent_node_id   = {authorize_sampler_node_id},
  component_config = {
    "state_var": "oauth_state"
  }
)
```

---

## Available EntraID Components

These components are registered in the JMeter MCP component registry and can
be added via `add_jmeter_component`:

| Component Type | Category | Purpose |
|----------------|----------|---------|
| `entra_state_preprocessor` | PreProcessor | Generates MSAL-format base64url `oauth_state` |
| `entra_wsfed_cookie_preprocessor` | PreProcessor | Injects `ESTSWCTXFLOWTOKEN` and `AADSSO` cookies |
| `boundary_extractor` | PostProcessor | Extracts values between left/right boundaries |
| `regex_extractor` | PostProcessor | Extracts values using regex with capture groups |
| `json_extractor` | PostProcessor | Extracts values using JSONPath expressions |
| `uuid_preprocessor` | PreProcessor | Generates UUID for `oauth_nonce`, `client_request_id` |
| `pkce_preprocessor` | PreProcessor | Generates PKCE `code_verifier` and `code_challenge` |

---

## Typical Sampler Sequence

Reference sequence for a full EntraID + WS-Federation + OpenAM login flow.
Use this as a mental model when diagnosing missing samplers or flow gaps.

| Step | Method | URL Pattern | Key Extractions |
|------|--------|-------------|-----------------|
| 1 | GET | `/oauth2/v2.0/authorize` | PreProcessors: PKCE, MSAL state, nonce, client_request_id. Extract: `oauth_code` from redirect |
| 2 | GET | `/oauth2/v2.0/authorize?sso_reload=True` | Only if BssoInterrupt. Extract: `flowToken_1`, `sCtx_1` from `$Config` |
| 3 | POST | `/common/GetCredentialType` | Extract: `federationRedirectUrl`, `estsrequest` |
| 4 | GET | `/openam/WSFederationServlet/...` | Federation redirect with `estsrequest` |
| 5 | POST | `/openam/json/authenticate` (step 1) | Extract: `AuthId` |
| 6 | POST | `/openam/json/authenticate` (step 2) | Extract: `AuthId`, `nonce` |
| 7 | POST | `/openam/json/authenticate` (step 3) | Extract: `AuthId`, `cdssoToken` |
| 8 | GET | OpenAM CDSSO redirect | Follows redirect chain |
| 9 | POST | WS-Fed form to `login.microsoftonline.com/.../wsfed` | Extract: `wresult` (boundary), `wctx` (regex), tenant GUID |
| 10 | POST | EntraID KMSI/processCredentials | PreProcessor: cookie injection. Extract: `flowToken_2`, `canary`, `sCtx`, `sessionId` |
| 11 | GET | Callback URL with `?code=` | Extract: `Code` from query string |
| 12 | POST | `/oauth2/v2.0/token` | Exchange code with PKCE verifier. Extract: `id_token` (JSON) |
| 13 | POST | Application token endpoint | Extract: `accessToken` (JSON) |

---

## Extractor Quick Reference

Complete list of extractors for the EntraID flow, with exact expressions.

| # | Sampler | Variable | Type | Expression |
|---|---------|----------|------|------------|
| 1 | authorize | `oauth_code` | Regex | `[#?&]code=([^&#\s]+)` |
| 2 | sign-in page | `flowToken_1` | Regex | `sFT":"(.*?)"` |
| 3 | sign-in page | `sCtx_1` | Regex | `"sCtx":"(.*?)"` |
| 4 | GetCredentialType | `federationRedirectUrl` | Regex | `FederationRedirectUrl":"(.*?)"` |
| 5 | GetCredentialType | `estsrequest` | Regex | `estsrequest%3d(.*?)"` |
| 6 | authenticate (1) | `AuthId` | Regex | `"authId":"(.*?)"` |
| 7 | authenticate (2) | `nonce_4` | Regex | `"nonce":"(.*?)==` |
| 8 | authenticate (3) | `AuthId` | Regex | `"authId":"(.*?)"` |
| 9 | authenticate (3) | `cdssoToken_2` | Regex | `"cdssoToken":"(.*?)"` |
| 10 | authenticate (4) | `cdssoToken_2` | Regex | `"cdssoToken":"(.*?)"` |
| 11 | WS-Fed return | `wsfed_1` | Regex | `com&#x2f;(.*?)&#x2f;wsfed"` |
| 12 | WS-Fed return | `wresult` | Boundary | L: `<input type="hidden" name="wresult" value="` R: `">` |
| 13 | WS-Fed return | `wctx_2` | Regex | `name="wctx" value="([^"]+)"` |
| 14 | KMSI page | `flowToken_2` | Regex | `sFT":"(.*?)","sFTName` |
| 15 | KMSI page | `Canary_2` | Regex | `"canary":"(.*?)"` |
| 16 | KMSI page | `sCTX` | Regex | `"sCtx":"(.*?)"` |
| 17 | KMSI page | `SessionID` | Regex | `sessionId":"(.*?)"` |
| 18 | callback | `Code` | Regex | `[?&]code=([^&"<\s]+)` |
| 19 | token endpoint | `entra_access_token` | JSON | `$.id_token` |
| 20 | app endpoint | `dds_access_token` | JSON | `$.data.currentUser.accessToken` |

---

## Network Capture Limitation

HAR files and Playwright network traces often have **empty response bodies**
for EntraID flows due to transparent Kerberos SSO and browser-level
authentication. This means:

- The correlation engine may not detect all EntraID-specific extractions from
  the network capture alone
- The agent should expect to add extractors manually during the debug loop
  after running smoke tests (which capture full responses)
- JMeter captures the full response bodies that browsers/DevTools cannot

This is a known limitation, not a bug. The diagnosis patterns and extractor
reference table in this skill exist precisely to help the agent add the
correct extractors without needing to rediscover them from scratch.
