# BlazeMeter MCP Workflow: Retrieving and Processing Test Results

This workflow retrieves performance test results from BlazeMeter, downloads test artifacts (JTL files, logs, etc.), processes the data, and generates aggregate performance reports. The processed results are stored locally and used as input for downstream workflows (Datadog and PerfAnalysis).

0. **Prerequisites:** Ask the user to provide:
   - BlazeMeter workspace name (e.g., "Quality Engineering", "Copilot Integration", etc.)
   - Test run ID (run_id)
   Do not proceed until both are provided.

1. **Get BlazeMeter workspaces** using `get_workspaces` to list all available workspaces.
   - Search for the workspace that matches the provided workspace name.
   - Extract the workspace_id from the matching workspace result.
   - If no matching workspace is found, report an error and ask the user to verify the workspace name.

2. **Get test run results** for the given performance test using run_id.
   - Extract and store the start_time and end_time from the test run results (required for downstream Datadog workflow).
   - If start/end times cannot be extracted from this step, fallback to extracting from the aggregate report in step 9.

3. **Get artifacts path**. This is the location of where test results will be stored in the cloud.

4. **Get artifact file list** for given run_id. If there is a failure, try getting the test run results again, and resume the workflow.

5. **Download artifacts zip** for given run_id.

6. **Extract artifact zip** for given run_id.

7. **Process extracted files** for given run_id.

8. **Get public report** for given run_id.

9. **Get aggregate report** for given run_id.

**NOTE:** If any of the above steps fail, please try again. The BlazeMeter test results are used downstream.

# Tasks:
1. Provide high-level summary and put into a table, including start/end times.
2. Next, proceed with Datadog MCP workflow.