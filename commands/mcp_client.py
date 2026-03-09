"""
MCP client for the learning computer. Connects to configured MCP servers (stdio),
discovers tools, converts them to Groq format, and executes tool calls.
Resolution in handle_cpu_mode: try MCP first; on failure or unknown tool, fall back to native.
"""
from __future__ import annotations

import logging
from typing import Any

import commands.config as config

logger = logging.getLogger(__name__)

# Optional MCP SDK imports (required for MCP_SERVERS to be used)
try:
    import anyio
    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    _MCP_AVAILABLE = True
except ImportError:
    anyio = None  # type: ignore[assignment]
    _MCP_AVAILABLE = False


def _mcp_tool_to_groq(tool: Any) -> dict:
    """Convert MCP Tool to Groq tools API format."""
    name = getattr(tool, "name", "unknown")
    description = getattr(tool, "description", "") or ""
    input_schema = (
        getattr(tool, "input_schema", None)
        or getattr(tool, "inputSchema", None)
        or {"type": "object", "properties": {}}
    )
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": input_schema,
        },
    }


def _call_tool_result_to_string(result: Any) -> str:
    """Extract text content from MCP CallToolResult."""
    if getattr(result, "is_error", False):
        return str(getattr(result, "content", "") or result)
    content = getattr(result, "content", None) or []
    parts = []
    for block in content:
        if hasattr(block, "type") and getattr(block, "type") == "text":
            parts.append(getattr(block, "text", ""))
        elif hasattr(block, "text"):
            parts.append(block.text)
    return "\n".join(parts) if parts else str(result)


async def _async_get_tools_and_mapping(servers: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    """
    Connect to each MCP server, list tools, convert to Groq format.
    Returns (merged_tools_list, tool_name -> server_config for that tool).
    """
    all_tools: list[dict] = []
    name_to_server: dict[str, dict] = {}
    if not _MCP_AVAILABLE or not servers:
        return all_tools, name_to_server
    for srv in servers:
        command = srv.get("command") or "npx"
        args = srv.get("args") or []
        params = StdioServerParameters(command=command, args=args)
        try:
            async with stdio_client(params) as (read_stream, write_stream):
                session = ClientSession(read_stream, write_stream)
                await session.initialize()
                list_result = await session.list_tools()
                for t in getattr(list_result, "tools", []):
                    groq_def = _mcp_tool_to_groq(t)
                    all_tools.append(groq_def)
                    name_to_server[t.name] = srv
        except Exception as e:
            logger.warning("MCP server %s failed to connect or list tools: %s", command, e)
    return all_tools, name_to_server


async def _async_call_tool(server_config: dict, name: str, arguments: dict[str, Any]) -> str | None:
    """Connect to the given MCP server and call the tool; return content string or None on failure."""
    if not _MCP_AVAILABLE:
        return None
    command = server_config.get("command") or "npx"
    args = server_config.get("args") or []
    params = StdioServerParameters(command=command, args=args)
    try:
        async with stdio_client(params) as (read_stream, write_stream):
            session = ClientSession(read_stream, write_stream)
            await session.initialize()
            result = await session.call_tool(name, arguments)
            return _call_tool_result_to_string(result)
    except Exception as e:
        logger.warning("MCP call_tool %s failed: %s", name, e)
        return None


def get_mcp_tools_groq_and_mapping() -> tuple[list[dict], dict[str, dict]]:
    """
    Sync entrypoint: get Groq-format tool list from all MCP servers and mapping tool_name -> server_config.
    """
    servers = getattr(config, "MCP_SERVERS", []) or []
    if not _MCP_AVAILABLE or not servers:
        return [], {}
    return anyio.run(_async_get_tools_and_mapping, servers)  # type: ignore[arg-type,union-attr]


def call_mcp_tool(server_config: dict, name: str, arguments: dict[str, Any]) -> str | None:
    """Sync entrypoint: call a tool on the given MCP server; return content string or None on failure."""
    if not _MCP_AVAILABLE:
        return None
    return anyio.run(_async_call_tool, server_config, name, arguments)  # type: ignore[arg-type,union-attr]

