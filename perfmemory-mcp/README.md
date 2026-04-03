# 🧠📚 PerfMemory MCP Server

Welcome to the PerfMemory MCP Server! 🚀  
This is a Python-based MCP server built with **FastMCP 2.0** that introduces a persistent "memory layer" for performance testing—enabling AI agents like Claude/Cursor to learn from past debugging sessions and apply those lessons to future JMeter script creation and troubleshooting.

Powered by a **pgvector database with HNSW indexing**, PerfMemory MCP stores structured debug sessions, failed attempts, and successful resolutions, allowing agents to query semantically similar issues before taking action. By leveraging embeddings and vector search, it transforms historical "lessons learned" into actionable intelligence—reducing trial-and-error and accelerating correlation analysis, script fixes, and performance test development.
