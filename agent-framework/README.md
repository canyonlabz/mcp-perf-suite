# PerfPilot Agents

AG2-based AI agent framework for the MCP Perf Suite. Runs in its own Docker
container (`perf-agents`) and orchestrates the performance testing pipeline
via the existing `perf-gateway` MCP servers, the `perfagent_state` database,
and the external Microsoft Playwright MCP container.

For architecture and design rationale, see
[../docs/plans/AG2-Framework-and-Architecture-V2.md](../docs/plans/AG2-Framework-and-Architecture-V2.md).

For development conventions and the folder map, see [AGENTS.md](./AGENTS.md).

Status: **under construction (Epic 3)**. The framework is not yet feature
complete - several agents currently respond with a documented "not_available"
message until their respective Features are implemented. See the V2 doc
Section 8 for the agent matrix.
