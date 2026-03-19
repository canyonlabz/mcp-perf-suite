# Correlation Naming Conventions Reference

This file contains the detailed schemas, naming tables, and examples for JMeter correlation
variable naming. It is read on-demand by the agent when detailed reference is needed.

---

## Input Schema (correlation_spec.json)

```jsonc
{
  "capture_file": "network_capture_*.json",
  "application": "string",
  "spec_version": "2.0",
  "analyzer_version": "2.0.0",
  "analysis_timestamp": "ISO8601 timestamp",
  "total_steps": number,
  "total_entries": number,
  "correlations": [
    {
      "correlation_id": "corr_1",
      "type": "business_id" | "correlation_id" | "oauth_param",
      "value_type": "business_id_numeric" | "business_id_guid" | "oauth_state" | "oauth_nonce" | "oauth_code" | "correlation_id",
      "confidence": "high" | "low",
      "correlation_found": true | false,
      "source": {
        "step_number": number,
        "step_label": "Step N: Description...",
        "entry_index": number,
        "request_id": "uuid",
        "request_method": "GET" | "POST" | etc,
        "request_url": "https://...",
        "response_status": number | null,
        "source_location": "response_json" | "response_header" | "response_redirect_url" | "request_url_path",
        "source_key": "field_name" | null,
        "source_json_path": "$.path.to.value" | null,
        "response_example_value": "actual_value"
      },
      "usages": [
        {
          "location_type": "request_url_path" | "request_query_param" | "request_header" | "request_body_json" | "request_body_form",
          "location_key": "param_name" | null,
          "location_json_path": "$.path" | null,
          "location_pattern": "param={VALUE}",
          "request_example_fragment": "snippet showing value in context",
          "usage_number": number,
          "entry_index": number,
          "step_number": number,
          "step_label": "Step N: Description...",
          "request_id": "uuid",
          "request_method": "GET" | "POST",
          "request_url": "https://..."
        }
      ],
      "parameterization_hint": {
        "strategy": "extract_and_reuse" | "csv_dataset" | "user_defined_variable",
        "extractor_type": "json" | "regex",
        "reason": "explanation"
      },
      "notes": "Optional notes for low-confidence or orphan IDs"
    }
  ],
  "summary": {
    "total_correlations": number,
    "business_ids": number,
    "correlation_ids": number,
    "oauth_params": number,
    "orphan_ids": number,
    "high_confidence": number,
    "low_confidence": number
  }
}
```

---

## Output Schema (correlation_naming.json)

```json
{
  "application": "<same as input application>",
  "spec_version": "2.0",
  "naming_conventions": {
    "case_style": "snake_case",
    "id_suffix": "_id",
    "token_suffix": "_token"
  },
  "variables": [
    {
      "correlation_id": "corr_1",
      "variable_name": "product_id",
      "jmeter_scope": "thread",
      "jmeter_extractor_type": "json_extractor",
      "jmeter_extractor_expression": "$.items[0].productId",
      "jmeter_extractor_name": "Extract product_id from ProductList response",
      "source_request_url": "https://api.example.com/products/list",
      "intended_usage": [
        "URL path parameter in product detail requests"
      ],
      "comments": "Business ID for product entity, extracted from product list response."
    }
  ],
  "orphan_variables": [
    {
      "correlation_id": "corr_15",
      "variable_name": "user_id",
      "parameterization_strategy": "csv_dataset",
      "csv_column_suggestion": "userId",
      "comments": "Numeric ID found in request URL but no source detected. Recommend CSV parameterization."
    }
  ]
}
```

---

## Variable Uniqueness Rules

Every `correlation_id` MUST have a unique `variable_name`. Duplicate variable names cause
JMeter scripts to fail because different values overwrite each other.

1. Never assign the same variable name to multiple correlations
2. Before finalizing output, verify ALL variable names are unique
3. If two correlations seem similar, differentiate using:
   - The `source.source_key` field name
   - The `usages[*].location_key` parameter name
   - A numeric suffix (`_1`, `_2`) as a last resort

### Common Duplicate Mistakes to Avoid

| BAD (Duplicates) | GOOD (Unique) | Reason |
|------------------|---------------|--------|
| `oauth_state` for both `state` and `client_id` | `oauth_state`, `oauth_client_id` | Different OAuth parameters |
| `oauth_state` for both `state` and `nonce` | `oauth_state`, `oauth_nonce` | Different OAuth parameters |
| `redirect_uri` for all redirect URLs | `oauth_redirect_uri`, `app_redirect_uri` | Different redirect contexts |
| `transaction_id` for multiple headers | `request_transaction_id`, `response_transaction_id` | Different source locations |

---

## OAuth Parameters — Required Variable Names

OAuth flows have many parameters. Each MUST have a distinct variable name:

| OAuth Parameter | Required Variable Name |
|-----------------|----------------------|
| `state` | `oauth_state` |
| `nonce` | `oauth_nonce` |
| `code` | `oauth_code` or `authorization_code` |
| `client_id` | `oauth_client_id` |
| `redirect_uri` | `oauth_redirect_uri` |
| `code_challenge` | `oauth_code_challenge` |
| `code_verifier` | `oauth_code_verifier` |
| `response_mode` | `oauth_response_mode` |
| `scope` | `oauth_scope` |
| `access_token` | `bearer_token` or `access_token` |
| `id_token` | `id_token` |
| `refresh_token` | `refresh_token` |

---

## Special Cases — URL Context Patterns

| URL/Context Pattern | Suggested Variable Name |
|---------------------|------------------------|
| `/cart` or "cart" in step | `cart_id` |
| `/order` or "order" in step | `order_id` |
| `/product` or "product" in step | `product_id` |
| `/user` or "user" in step | `user_id` |
| `/customer` | `customer_id` |
| `/item` | `item_id` |
| `/account` | `account_id` |
| OAuth `state` parameter | `oauth_state` |
| OAuth `nonce` parameter | `oauth_nonce` |
| OAuth `client_id` | `oauth_client_id` |

---

## Extractor Expressions

### JSON Extractor

When `source_location` is `response_json`, use `source.source_json_path` directly:

```
jmeter_extractor_expression: "$.items[0].productId"
```

### Regex Extractor

When `source_location` is `response_header` or `response_redirect_url`:

```
jmeter_extractor_expression: "transactionid:\\s*([^\\r\\n]+)"
jmeter_extractor_expression: "[?&]code=([^&]+)"
```

---

## Orphan Variable Naming Rules

For correlations where `correlation_found: false`.

### Quality Requirements

Orphan variable names MUST NOT be:
- Empty/blank
- Just a number suffix like `_22`, `_23`
- Generic names like `value` or `value_19`

### Naming Strategy

1. **If `source_key` exists and is meaningful** — use it directly
   - `source_key: "pageSize"` -> `page_size`
   - `source_key: "appGuid"` -> `app_guid`
   - `source_key: "teamId"` -> `team_id`

2. **If `source_key` is `"_"` (underscore)** — cache-busting timestamp
   - Common in SignalR, jQuery AJAX calls
   - Name as `signalr_timestamp_N` or `cache_timestamp_N` where N is the step number

3. **If `source_key` is null and `source_location` is `"request_url_path"`**
   - Examine the `request_url` to infer context
   - `/ProductWidget/1` -> `widget_id` or `product_widget_id`
   - `/api/users/123` -> `user_id`

4. **If `source_key` is null and no context is available**
   - Use `orphan_<step_number>_<entry_index>` format

### Orphan Parameterization Strategies

- `csv_dataset` for IDs appearing 3+ times
- `user_defined_variable` for IDs appearing 1-2 times
- Provide `csv_column_suggestion` that matches the variable name

---

## SignalR / WebSocket Patterns

| Pattern in URL | source_key | Variable Name |
|----------------|------------|---------------|
| `/signalr/negotiate?...&_=timestamp` | `_` | `signalr_timestamp_N` |
| `/signalr/start?...&_=timestamp` | `_` | `signalr_start_timestamp_N` |
| `/signalr/connect?...&connectionToken=` | `connectionToken` | `signalr_connection_token` |
| `/signalr/...&connectionData=` | `connectionData` | `signalr_connection_data` |

---

## URL Path Segment Naming

When `source_location: "request_url_path"` and `source_key: null`:

| URL Pattern | Example Value | Variable Name |
|-------------|---------------|---------------|
| `/api/.../Widget/N` | `1`, `2` | `widget_id` |
| `/api/.../User/N` | `12345` | `user_id` |
| `/api/.../Product/N` | `1119216` | `product_id` |
| `/api/.../Report/N` | `456` | `report_id` |
| Path segment is GUID | `326BABA4-...` | `path_guid` |

**Rule: Extract the noun from the URL path preceding the value.**

---

## Example Transformation

**Input (from correlation_spec.json):**

```json
{
  "correlation_id": "corr_7",
  "type": "business_id",
  "value_type": "business_id_numeric",
  "confidence": "high",
  "correlation_found": true,
  "source": {
    "step_number": 4,
    "step_label": "Step 4: Navigate to the Products page.",
    "request_url": "https://api.example.com/catalog/products/list",
    "source_location": "response_json",
    "source_key": "productId",
    "source_json_path": "$.items[0].productId",
    "response_example_value": "12345"
  },
  "usages": [
    {
      "location_type": "request_url_path",
      "request_url": "https://api.example.com/catalog/products/details/12345"
    }
  ]
}
```

**Output (in correlation_naming.json):**

```json
{
  "correlation_id": "corr_7",
  "variable_name": "product_id",
  "jmeter_scope": "thread",
  "jmeter_extractor_type": "json_extractor",
  "jmeter_extractor_expression": "$.items[0].productId",
  "jmeter_extractor_name": "Extract product_id from ProductList response",
  "source_request_url": "https://api.example.com/catalog/products/list",
  "intended_usage": [
    "URL path parameter in product details API calls"
  ],
  "comments": "Product ID extracted from catalog list response, used in product detail endpoints."
}
```

---

## Bad Example — Duplicate Variable Names (DO NOT DO THIS)

**BAD Output (duplicates cause script failure):**

```json
{
  "variables": [
    { "correlation_id": "corr_1", "variable_name": "oauth_state", "source_key": "client_id" },
    { "correlation_id": "corr_2", "variable_name": "oauth_state", "source_key": "state" },
    { "correlation_id": "corr_3", "variable_name": "oauth_state", "source_key": "nonce" }
  ]
}
```

**CORRECT Output (each correlation has unique variable name):**

```json
{
  "variables": [
    { "correlation_id": "corr_1", "variable_name": "oauth_client_id", "source_key": "client_id" },
    { "correlation_id": "corr_2", "variable_name": "oauth_state", "source_key": "state" },
    { "correlation_id": "corr_3", "variable_name": "oauth_nonce", "source_key": "nonce" }
  ]
}
```
