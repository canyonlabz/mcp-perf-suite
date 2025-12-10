# 📘 **Datadog APM & Log Query Guide**

### *A visual & intuitive guide to building queries inside the Datadog MCP Server*

---

# 🎯 1. Overview

The Datadog MCP Server supports a flexible, layered system for defining and executing both **APM Trace** and **Log Search** queries.

Queries can come from multiple sources:

| Source                                                 | Meaning                                   |
| ------------------------------------------------------ | ----------------------------------------- |
| 🔧 **Built-in templates**                              | Immediate, environment-tag driven queries |
| 🧩 **Environment-aware templates**                     | Queries built from services, hosts, k8s   |
| ✍️ **Inline custom queries**                           | User supplies raw Datadog query           |
| 📁 **Reusable custom queries** (`custom_queries.json`) | User-based, shareable templates           |

---

# 🧠 2. Query Resolution Order (Priority System)

When a tool receives a `query_type`, it resolves it in this strict order:

| Priority | Source                       | Description                                                    |
| -------- | ---------------------------- | -------------------------------------------------------------- |
| **1**    | Inline custom query          | `"custom"` + `custom_query` wins over everything               |
| **2**    | Built-in template            | Standard templates like `all_errors`, `slow_requests`          |
| **3**    | `custom_queries.json`        | Reusable global user-based templates                           |
| **4**    | Env-driven dynamic templates | `service_errors`, `host_errors`, `kubernetes_errors`           |

---

# 🚀 3. Built-in APM Templates

Templates that work anywhere without extra configuration.

| Query Type        | Description         | Example                          |
| ----------------- | ------------------- | -------------------------------- |
| `all_errors`      | All error traces    | `env:uat status:error`           |
| `http_500_errors` | HTTP 500 exceptions | `@http.status_code:500`          |
| `http_errors`     | Any 4xx/5xx         | `@http.status_code:[400 TO 599]` |
| `slow_requests`   | Requests >1s        | `@duration:>1000000000`          |

---

# 📊 4. Built-in Log Templates

| Query Type    | Description            | Example                                          | 
| ------------- | ---------------------- | ------------------------------------------------ | 
| `all_errors`  | Error-level logs       | `status:error OR level:ERROR`                    |
| `warnings`    | Warning logs           | `level:WARNING`                                  | 
| `http_errors` | HTTP errors in logs    | `@http.status_code:[400 TO 599]`                 | 
| `api_errors`  | API logs with failures | `@http.method:* AND @http.status_code:[400-599]` |

---

# 🏗️ 5. Environment-Based Dynamic Templates

These depend on what’s defined inside `environments.json`.

---

## 🔧 5.1 `service_errors`

Given:

```json
"services": [
  {"service_name": "checkout-api"},
  {"service_name": "auth-service"}
]
```

Generated query:

```
(env:uat) AND (service:checkout-api OR service:auth-service) AND status:error
```

---

## 🖥️ 5.2 `host_errors`

Given:

```json
"hosts": [
  {"hostname": "vm001"},
  {"hostname": "vm002"}
]
```

Generated query:

```
(env:uat) AND (host:vm001 OR host:vm002) AND status:error
```

---

## ☸️ 5.3 `kubernetes_errors`

Given:

```json
"kubernetes": {
  "services": [
    {"service_filter": "auth-*"},
    {"service_filter": "orders-api"}
  ]
}
```

Generated query:

```
(env:uat) AND (kube_service:auth-* OR kube_service:orders-api) AND status:error
```

---

# ✍️ 6. Inline Custom Query (Maximum Flexibility)

Set:

```json
{
  "query_type": "custom",
  "custom_query": "service:auth-api env:uat @duration:>5000000000"
}
```

You are giving the Datadog search engine the exact query to execute.
No templates apply.

---

# 📁 7. Global Custom Queries via `custom_queries.json`

This is the recommended way to define reusable project-level queries.

---

## 📁 File Location

```
datadog-mcp/custom_queries.json
```

---

## 📁 File Structure

```jsonc
{
  "schema_version": "1.0",

  "projects": {
    "vipr": {
      "description": "VIPR Valuation Services",
      "apm_queries": ["vipr_500_errors", "vipr_slow_requests"],
      "log_queries": ["vipr_error_logs"]
    }
  },

  "apm_queries": {
    "vipr_500_errors": {
      "description": "VIPR HTTP 500 errors",
      "query": "service:valuationservice env:uat @http.status_code:500"
    }
  },

  "log_queries": {
    "vipr_error_logs": {
      "description": "VIPR Application errors",
      "query": "service:valuationservice status:error"
    }
  }
}
```

---

# 🕰️ 8. Legacy Environment Custom Queries (Optional)

Still supported for backward compatibility:

```json
"custom_log_queries": {
  "old_filter": {
    "query": "service:legacy status:error"
  }
}
```

Emoji meaning: 🕰️ = deprecated but supported for now.

---

# 🧮 9. Summary of All Query Sources

| Source                                | Description                | Recommended?         |
| ------------------------------------- | -------------------------- | -------------------- |
| Built-in templates                    | Common patterns            | ✅ Yes                |
| Env-based queries                     | Service/host/k8s filtering | ✅ Yes                |
| Inline custom                         | Fully manual               | ⚠️ Use when needed   |
| Global custom (`custom_queries.json`) | Reusable                   | 🌟 **Best practice** |

---

# 🧪 10. Example MCP Tool Usage

## 🔵 APM Example

```json
{
  "env_name": "uat",
  "query_type": "vipr_500_errors",
  "start_time": "2024-12-01T00:00:00Z",
  "end_time": "2024-12-02T00:00:00Z"
}
```

## 🟠 Logs Example

```json
{
  "env_name": "qa",
  "query_type": "service_errors",
  "start_time": "2024-12-05T00:00:00Z",
  "end_time": "2024-12-05T23:59:59Z"
}
```
