# Performance Test Comparison Report
**Generated:** {{GENERATED_TIMESTAMP}}  
**Test Runs Analyzed:** {{RUN_COUNT}}  
**Environment:** {{ENVIRONMENT}}  
**MCP Version:** {{MCP_VERSION}}

> **Note:** This report compares {{RUN_COUNT}} test runs. For optimal readability, a maximum of 5 runs is recommended. Comparing more than 5 runs may reduce report clarity for stakeholders.

---

## 1.0 Executive Summary

{{EXECUTIVE_SUMMARY}}

### 1.1 Key Findings
{{KEY_FINDINGS_BULLETS}}

### 1.2 Overall Performance Trend
{{OVERALL_TREND_SUMMARY}}

---

## 2.0 Test Configurations

| Configuration Item | {{RUN_1_LABEL}} | {{RUN_2_LABEL}} | {{RUN_3_LABEL}} | {{RUN_4_LABEL}} | {{RUN_5_LABEL}} |
|--------------------|-----------------|-----------------|-----------------|-----------------|-----------------|
| **Test Run ID** | {{RUN_1_ID}} | {{RUN_2_ID}} | {{RUN_3_ID}} | {{RUN_4_ID}} | {{RUN_5_ID}} |
| **Test Date** | {{RUN_1_DATE}} | {{RUN_2_DATE}} | {{RUN_3_DATE}} | {{RUN_4_DATE}} | {{RUN_5_DATE}} |
| **Test Duration** | {{RUN_1_DURATION}} | {{RUN_2_DURATION}} | {{RUN_3_DURATION}} | {{RUN_4_DURATION}} | {{RUN_5_DURATION}} |
| **Total Samples** | {{RUN_1_SAMPLES}} | {{RUN_2_SAMPLES}} | {{RUN_3_SAMPLES}} | {{RUN_4_SAMPLES}} | {{RUN_5_SAMPLES}} |
| **Success Rate** | {{RUN_1_SUCCESS_RATE}}% | {{RUN_2_SUCCESS_RATE}}% | {{RUN_3_SUCCESS_RATE}}% | {{RUN_4_SUCCESS_RATE}}% | {{RUN_5_SUCCESS_RATE}}% |
| **Environment** | {{RUN_1_ENV}} | {{RUN_2_ENV}} | {{RUN_3_ENV}} | {{RUN_4_ENV}} | {{RUN_5_ENV}} |
| **Test Type** | {{RUN_1_TYPE}} | {{RUN_2_TYPE}} | {{RUN_3_TYPE}} | {{RUN_4_TYPE}} | {{RUN_5_TYPE}} |

---

## 3.0 Issues Observed

{{ISSUES_SUMMARY}}

### 3.1 Critical Issues

{{CRITICAL_ISSUES_TABLE}}

### 3.2 Performance Degradations

| Issue Category | Severity | Affected Runs | Description |
|----------------|----------|---------------|-------------|
{{PERFORMANCE_DEGRADATIONS_ROWS}}

### 3.3 Infrastructure Concerns

| Concern | Resource Type | Affected Runs | Details |
|---------|--------------|---------------|---------|
{{INFRASTRUCTURE_CONCERNS_ROWS}}

### 3.4 Error Rate Comparison

| Run | Total Errors | Error Rate (%) | Δ vs Previous Run | Top Error Type |
|-----|--------------|----------------|-------------------|----------------|
| {{RUN_1_LABEL}} | {{RUN_1_ERROR_COUNT}} | {{RUN_1_ERROR_RATE}} | - | {{RUN_1_TOP_ERROR}} |
| {{RUN_2_LABEL}} | {{RUN_2_ERROR_COUNT}} | {{RUN_2_ERROR_RATE}} | {{RUN_2_ERROR_DELTA}} | {{RUN_2_TOP_ERROR}} |
| {{RUN_3_LABEL}} | {{RUN_3_ERROR_COUNT}} | {{RUN_3_ERROR_RATE}} | {{RUN_3_ERROR_DELTA}} | {{RUN_3_TOP_ERROR}} |
| {{RUN_4_LABEL}} | {{RUN_4_ERROR_COUNT}} | {{RUN_4_ERROR_RATE}} | {{RUN_4_ERROR_DELTA}} | {{RUN_4_TOP_ERROR}} |
| {{RUN_5_LABEL}} | {{RUN_5_ERROR_COUNT}} | {{RUN_5_ERROR_RATE}} | {{RUN_5_ERROR_DELTA}} | {{RUN_5_TOP_ERROR}} |

**Summary:** {{ERROR_RATE_SUMMARY}}

### 3.5 Bugs to Create

**Action Items:** The following bugs should be created in your tracking system (Azure DevOps, Jira, etc.):

#### Bug Placeholder 1
- **Title:** {{BUG_1_TITLE}}
- **Environment:** {{BUG_1_ENVIRONMENT}}
- **Affected Run(s):** {{BUG_1_RUNS}}
- **Severity:** {{BUG_1_SEVERITY}}

#### Bug Placeholder 2
- **Title:** {{BUG_2_TITLE}}
- **Environment:** {{BUG_2_ENVIRONMENT}}
- **Affected Run(s):** {{BUG_2_RUNS}}
- **Severity:** {{BUG_2_SEVERITY}}

#### Bug Placeholder 3
- **Title:** {{BUG_3_TITLE}}
- **Environment:** {{BUG_3_ENVIRONMENT}}
- **Affected Run(s):** {{BUG_3_RUNS}}
- **Severity:** {{BUG_3_SEVERITY}}

#### Bug Placeholder 4
- **Title:** {{BUG_4_TITLE}}
- **Environment:** {{BUG_4_ENVIRONMENT}}
- **Affected Run(s):** {{BUG_4_RUNS}}
- **Severity:** {{BUG_4_SEVERITY}}

#### Bug Placeholder 5
- **Title:** {{BUG_5_TITLE}}
- **Environment:** {{BUG_5_ENVIRONMENT}}
- **Affected Run(s):** {{BUG_5_RUNS}}
- **Severity:** {{BUG_5_SEVERITY}}

> **Note:** Use the ADO MCP Server to auto-generate detailed bug descriptions and create work items programmatically.

---

## 4.0 API Performance Comparison

**Focus:** APIs exceeding SLA thresholds or showing significant regression across test runs

### 4.1 SLA Violations by Run

| API Name | SLA Threshold (ms) | {{RUN_1_LABEL}} | {{RUN_2_LABEL}} | {{RUN_3_LABEL}} | {{RUN_4_LABEL}} | {{RUN_5_LABEL}} | Trend |
|----------|-------------------|-----------------|-----------------|-----------------|-----------------|-----------------|-------|
{{API_COMPARISON_ROWS}}

**Legend:**
- ✅ Met SLA
- ❌ Exceeded SLA
- ⬆️ **Improved** (response time decreased)
- ⬇️ **Degraded** (response time increased)
- ➡️ **Stable** (±5% or less)

### 4.2 Top Response Time Offenders

**APIs with consistently high response times across runs:**

| API Name | {{RUN_1_LABEL}} (ms) | {{RUN_2_LABEL}} (ms) | {{RUN_3_LABEL}} (ms) | {{RUN_4_LABEL}} (ms) | {{RUN_5_LABEL}} (ms) | Avg Δ |
|----------|---------------------|---------------------|---------------------|---------------------|---------------------|-------|
{{TOP_OFFENDERS_ROWS}}

### 4.3 Throughput Comparison

| Metric | {{RUN_1_LABEL}} | {{RUN_2_LABEL}} | {{RUN_3_LABEL}} | {{RUN_4_LABEL}} | {{RUN_5_LABEL}} | Trend |
|--------|-----------------|-----------------|-----------------|-----------------|-----------------|-------|
| **Avg Throughput (req/sec)** | {{RUN_1_AVG_THROUGHPUT}} | {{RUN_2_AVG_THROUGHPUT}} | {{RUN_3_AVG_THROUGHPUT}} | {{RUN_4_AVG_THROUGHPUT}} | {{RUN_5_AVG_THROUGHPUT}} | {{THROUGHPUT_TREND}} |
| **Peak Throughput (req/sec)** | {{RUN_1_PEAK_THROUGHPUT}} | {{RUN_2_PEAK_THROUGHPUT}} | {{RUN_3_PEAK_THROUGHPUT}} | {{RUN_4_PEAK_THROUGHPUT}} | {{RUN_5_PEAK_THROUGHPUT}} | {{PEAK_THROUGHPUT_TREND}} |

**Summary:** {{THROUGHPUT_SUMMARY}}

---

## 5.0 Infrastructure Metrics Comparison

### 5.1 CPU Utilization

| Service/Host | {{RUN_1_LABEL}} | {{RUN_2_LABEL}} | {{RUN_3_LABEL}} | {{RUN_4_LABEL}} | {{RUN_5_LABEL}} | Trend | Δ vs Run 1 |
|--------------|-----------------|-----------------|-----------------|-----------------|-----------------|-------|------------|
{{CPU_COMPARISON_ROWS}}

**Summary:**
- **Improved:** {{CPU_IMPROVED_COUNT}} service(s) ⬆️
- **Degraded:** {{CPU_DEGRADED_COUNT}} service(s) ⬇️
- **Stable:** {{CPU_STABLE_COUNT}} service(s) ➡️

### 5.2 Memory Utilization

| Service/Host | {{RUN_1_LABEL}} | {{RUN_2_LABEL}} | {{RUN_3_LABEL}} | {{RUN_4_LABEL}} | {{RUN_5_LABEL}} | Trend | Δ vs Run 1 |
|--------------|-----------------|-----------------|-----------------|-----------------|-----------------|-------|------------|
{{MEMORY_COMPARISON_ROWS}}

**Summary:**
- **Improved:** {{MEMORY_IMPROVED_COUNT}} service(s) ⬆️
- **Degraded:** {{MEMORY_DEGRADED_COUNT}} service(s) ⬇️
- **Stable:** {{MEMORY_STABLE_COUNT}} service(s) ➡️

### 5.3 Resource Efficiency Assessment

{{RESOURCE_EFFICIENCY_SUMMARY}}

---

## 6.0 Correlation Insights (Optional)

{{CORRELATION_INSIGHTS_SECTION}}

**Key Observations:**
{{CORRELATION_KEY_OBSERVATIONS}}

> **Note:** This section is included only when significant performance-infrastructure correlations are detected (e.g., high CPU causing response time spikes).

---

## 7.0 Conclusion

### 7.1 Synopsis

{{CONCLUSION_SYNOPSIS}}

### 7.2 Recommendations

{{RECOMMENDATIONS_LIST}}

### 7.3 Next Steps

{{NEXT_STEPS_LIST}}

---

## Appendix A: Test Run Metadata

### Source Files by Run

**{{RUN_1_LABEL}} ({{RUN_1_ID}})**
{{RUN_1_SOURCE_FILES}}

**{{RUN_2_LABEL}} ({{RUN_2_ID}})**
{{RUN_2_SOURCE_FILES}}

**{{RUN_3_LABEL}} ({{RUN_3_ID}})**
{{RUN_3_SOURCE_FILES}}

**{{RUN_4_LABEL}} ({{RUN_4_ID}})**
{{RUN_4_SOURCE_FILES}}

**{{RUN_5_LABEL}} ({{RUN_5_ID}})**
{{RUN_5_SOURCE_FILES}}

### Report Generation Details
- **Report Generated By:** PerfReport MCP Server
- **MCP Version:** {{MCP_VERSION}}
- **Generation Timestamp:** {{GENERATED_TIMESTAMP}}
- **Runs Compared:** {{RUN_IDS_LIST}}
- **Comparison Method:** Sequential run-to-run analysis

---

*End of Comparison Report*
