---
name: ado-test-case-conversion
description: >-
  Convert Azure DevOps (ADO) QA Functional test cases into browser automation Markdown
  specs for JMeter MCP. Use when the user mentions ADO test cases, Azure DevOps
  conversion, QA functional to performance, or test case format migration.
---

# ADO to JMeter MCP Browser Automation Conversion

## When to Use This Skill

- User wants to convert Azure DevOps test cases into performance test specs
- User mentions ADO, Azure DevOps, QA functional test cases, or test case conversion
- User has test case steps from ADO and needs a Markdown spec for the JMeter MCP
  `get_browser_steps` tool

---

## Reference

This section provides context for humans and capable models. For the step-by-step
execution instructions, skip to the **Execution** section below.

### What This Workflow Does

Converts QA Functional test cases from Azure DevOps (ADO) into Markdown files that the
JMeter MCP `get_browser_steps` tool can parse. This bridges the gap between QA Functional
(Playwright-based testing) and QA Performance (JMeter script generation) teams.

### Azure DevOps Access Requirement

This workflow requires access to Azure DevOps to pull test case steps. The user must have:
- **ADO MCP server** configured and running (for automated pull), or
- **Manual access** to Azure DevOps to copy/paste test case steps into a `.txt` file

If neither is available, the workflow cannot proceed. Inform the user and stop.

### Target Format Requirements

The JMeter MCP spec parser requires:

- **Step labels** (case-insensitive, at line start): `Step`, `TC`, `TS`, `Test Case`, `Test Step`
- **Terminal keyword** (required, at end): `END TASK`, `TERMINATE`, `END FLOW`, or `END`
- **Continuation lines**: Indented sub-bullets with `-` are kept as part of the current step
- **No metadata/headers**: Optional titles are ignored; no structured frontmatter needed
- **Recommended label format**: `Step 1:`, `Step 2:`, etc.

### Conversion Rules (9 Rules)

**Rule 1: Remove ADO Formatting Artifacts**
Strip section comment blocks (`// ===...`), dividers, and blank padding lines.
If section context is needed, fold it into the step's natural language.

**Rule 2: Renumber Steps Sequentially**
ADO test cases have non-sequential numbering. Renumber to `Step 1` through `Step N`.

**Rule 3: Replace Placeholder Variables**
Replace `{{placeholder}}` syntax with actual values from the user.
Same placeholder across multiple steps = same concrete value everywhere.
If no values are provided, ask the user before converting.

**Rule 4: Expand Login/Authentication Step**
ADO steps assume auth is separate. Add an explicit login step.
- SSO: `Step 1: Navigate to <URL>. If redirected to a login page, enter the email and click 'Next'. The site uses SSO so no password is required. Else, skip this step.`
- Standard: `Step 1: Navigate to <URL>. If redirected to a login page, enter username and password, then click 'Sign in'. Else, skip this step.`
- No auth: Skip this pattern for public-facing apps.

**Rule 5: Write Steps as Natural Language for Playwright**
Steps are executed by an AI agent using Playwright. Write clear instructions:
- Navigate: "Navigate to https://example.com/"
- Click: "Click on 'Laptops' under the 'Categories' menu"
- Type/Fill: "Type 'MacBook Pro' into the 'Search' textbox"
- Select: "Select 'United States' from the 'Country' dropdown"
- Verify: "Verify the text 'Order placed' is displayed"
- Conditional: "If a pop-up appears, click 'Ok'; otherwise continue"

**Rule 6: Preserve Shadow-Root References**
Keep "inside shadow-root" context for Playwright shadow DOM handling.

**Rule 7: Use Sub-Bullets for Multi-Item Steps**
Form fills and multi-action steps use indented `-` sub-bullets:

```
Step 7: Fill in the form with the following details:
    - Name: John Wick
    - Country: United States
    - City: New York
    - Credit card: 4111111111111111
```

**Rule 8: Add Standard Closing Pattern**
Final step must keep the browser open and end with a terminal keyword:

```
Step N: <final verification step>.
    - Confirm the flow is completed and notify the user that the browser will remain open for manual inspection.
    - Do not close the browser.
END TASK
```

**Rule 9: File Naming Convention**
Use kebab-case or snake_case: `<application>-<workflow-description>.md`
Examples: `blazedemo-product-purchase.md`, `myapp-user-registration.md`

### Related Rules

These Cursor Rules apply when using this skill:

- **`prerequisites.mdc`** — Azure DevOps access validation (see prerequisite table above)
- **`skill-execution-rules.mdc`** — Follow steps in order, collect inputs first, do not skip
- **`browser-safety.mdc`** — Applies when the converted spec is used in Playwright browser automation

### Tips and Lessons Learned

- **Date formats**: Note datepicker input format (e.g., `MM/dd/yyyy`) when known.
- **Combobox vs dropdown**: Preserve the original UI component reference if specified.
- **Authentication**: Adapt login step to the app's auth method. Always include credentials.
- **Think time**: Browser automation rules handle think time separately. Do not encode waits.
- **Pop-ups and dialogs**: Add conditional handling for confirmation dialogs and alerts.

---

## Execution

Follow these steps exactly, in order. Each step has one action.

---

### Collect Inputs

Ask the user for the following values. Do not proceed until all required values are collected.

```
REQUIRED:
  ado_source      = [ADO test case URL, or path to .txt file with copy/pasted steps]
  app_name        = [application name, e.g., "blazedemo"]
  flow_name       = [workflow name, e.g., "product-purchase"]
  auth_method     = [SSO, standard, or none]

CONDITIONAL:
  login_email     = [required if auth_method is SSO]
  login_username  = [required if auth_method is standard]
  login_password  = [required if auth_method is standard]
  login_url       = [required if auth_method is SSO or standard]

OPTIONAL:
  placeholder_values = [replacements for any {{placeholder}} variables in the ADO steps]
```

---

### Step 1 — Obtain the ADO Test Case

**Input:** `ado_source`

**Action:** Get the raw ADO test case steps into a `.txt` file.

- If the user provides a `.txt` file path: Read that file.
- If using ADO MCP: Pull the test case steps and save to
  `jmeter-mcp/test-specs/azure-devops/{app_name}-{flow_name}.txt`
- If the user pastes the steps directly: Save them to the same path.

**Save:** `raw_steps` = the raw ADO test case text.

**On error:** If no test case steps can be obtained, stop. Inform the user.

---

### Step 2 — Convert Using All 9 Rules

**Input:** `raw_steps`, `auth_method`, credentials, `placeholder_values`

**Action:** Apply all 9 conversion rules from the Reference section to `raw_steps`:

1. Remove ADO formatting artifacts (comment blocks, dividers)
2. Renumber steps sequentially (`Step 1:` through `Step N:`)
3. Replace `{{placeholder}}` variables with user-provided values
4. Add login/authentication step based on `auth_method`
5. Write all steps as natural language for Playwright
6. Preserve any shadow-root references
7. Use sub-bullets for multi-item steps (form fills)
8. Add standard closing pattern (keep browser open + `END TASK`)
9. Generate filename as `{app_name}-{flow_name}.md`

**Save:** `converted_spec` = the fully converted Markdown content.

---

### Step 3 — Save the Output

**Input:** `converted_spec`, `app_name`, `flow_name`

**Action:** Write `converted_spec` to:

```
jmeter-mcp/test-specs/web-flows/{app_name}-{flow_name}.md
```

**Save:** `spec_path` = the full path to the saved file.

**On error:** If the file cannot be written, stop. Report the error to the user.

---

### Step 4 — Report to User

**Input:** `spec_path`, `converted_spec`

**Action:** Present the results to the user.

Tell the user:
- The converted spec was saved to `{spec_path}`
- Show the full converted spec content for review
- The spec is ready for use with `get_browser_steps` in the Playwright workflow

Ask the user:
- "Does the converted spec look correct?"
- "Do you want to adjust any steps before proceeding?"

---

## Example: Before and After

**ADO Source** (saved in `test-specs/azure-devops/demoblaze-purchase.txt`):

```
// SECTION 1: Browse Products
1. Navigate to https://demoblaze.com/
2. Click on 'Laptops' under Categories
3. Select 'MacBook Pro' and add to cart

// SECTION 2: Checkout
10. Go to the Cart
12. Place the order
15. Fill in checkout form with {{Customer Name}}, {{Country}}, {{City}}, {{Credit Card}}
16. Complete the purchase
```

**Converted Output** (saved in `test-specs/web-flows/blazedemo-product-purchase.md`):

```
Step 1: Navigate to https://demoblaze.com/.
Step 2: Click on 'Laptops' under the 'Categories' menu.
Step 3: Select 'MacBook Pro' and click on 'Add to cart'.
Step 4: If a pop-up appears, click 'Ok' to proceed; otherwise continue to the next step.
Step 5: Click on 'Cart' from the top menu.
Step 6: On the 'Products' page, click on 'Place Order'.
Step 7: Fill in the form with the following details:
    - Name: John Wick
    - Country: United States
    - City: New York
    - Credit card: 4111111111111111
    - Month: 12
    - Year: 2029
After filling out form details click on 'Purchase' to complete the order and wait for confirmation. After confirmation, click 'Ok' button.
Step 8: User will be redirected to the main 'Product Store' page.
    - Confirm the flow is completed and notify the user that the browser will remain open for manual inspection.
    - Do not close the browser.
END TASK
```

---

## Error Handling

These rules apply to every step:

- If a required input is missing, ask the user for it before proceeding.
- If `{{placeholder}}` variables exist and the user has not provided replacement values,
  ask before converting. Do not guess.
- Do NOT proceed to the next step if the current step failed.
- Ask the user for next steps on any error.
