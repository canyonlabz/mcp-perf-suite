import asyncio
from fastmcp import FastMCP, Context  # ✅ FastMCP 2.x import
from utils.config import load_config, load_workflow_config
from utils.workflow_utils import (
    interpolate_params, 
    prerequisites_satisfied, 
    dispatch_tool, 
    poll_until_complete
)

async def execute_blazemeter_workflow(ctx: Context, tool_registry: dict):
    await ctx.info("Starting BlazeMeter workflow execution...")

    if ctx is None:
        await ctx.error("Context is None for workflow execution.")
        return

    if tool_registry is None:
        await ctx.error("Tool registry is None for workflow execution.")
        return

    config = load_config()
    workflow_steps = load_workflow_config()
    bz_config = config.get("blazemeter", {})

    for step in workflow_steps:
        prereq_ok = await prerequisites_satisfied(ctx, step)
        if step.get("optional") and not prereq_ok:
            await ctx.info(f"Skipping optional step '{step['tool']}' due to unsatisfied prerequisites.")
            continue

        params = await interpolate_params(step["params"], ctx, bz_config)
        retry = step.get("on_error", {}).get("retry", bz_config.get("polling_max_retries", 3))
        exit_on_error = step.get("on_error", {}).get("exit_on_error", False)
        notify_user = step.get("on_error", {}).get("notify_user", False)
        output_key = step.get("output")
        retry_count = 0

        while retry_count <= retry:
            try:
                if step.get("repeat_until"):
                    result = await poll_until_complete(step, params, ctx, bz_config, tool_registry)
                else:
                    result = await dispatch_tool(step["tool"], params, ctx, tool_registry)

                if output_key:
                    val = result if not isinstance(result, dict) else result.get(output_key, result)
                    await ctx.set_state(output_key, val)

                await ctx.info(f"Step '{step['tool']}' executed successfully.")
                break
            except Exception as e:
                retry_count += 1
                error_msg = f"Step '{step['tool']}' failed (attempt {retry_count}): {str(e)}"
                if notify_user:
                    await ctx.error(error_msg)
                if retry_count > retry or (exit_on_error or step['tool'] == "start_test"):
                    await ctx.error(f"Workflow aborted on error in '{step['tool']}': {str(e)}")
                    await ctx.set_state("workflow_aborted", True)
                    return
                await ctx.info(f"Retrying step '{step['tool']}' (attempt {retry_count}/{retry})...")

    await ctx.info("Workflow complete.")
