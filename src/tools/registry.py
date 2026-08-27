# This Script defines the shared shape every tool category (computer_use, filesystem, browser_use,
# memory) plugs into. Mirrors src/mcps/registry.py's interface EXACTLY on purpose: list_openai_tools()
# and call_tool(name, arguments) -> str, same signatures -- so whatever eventually dispatches the
# model's tool_calls can treat native tools and MCP tools uniformly, without caring which is which.
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    """
    One callable capability. `parameters` is a JSON Schema object (same shape
    OpenAI/MCP both expect). `handler` is called as handler(**arguments) --
    write handler functions with normal typed keyword parameters matching
    the schema's properties, not a single dict argument.
    """
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., str]


class ToolRegistry:
    """Collects Tools from every category and dispatches by name. Never raises -- a bad call becomes a 'Tool error: ...' string, same contract as MCPRegistry.call_tool."""

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register_all(self, tools: List[Tool]) -> None:
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"Tool '{tool.name}' is already registered -- names must be unique across every category")
            self._tools[tool.name] = tool

    def list_openai_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Tool error: unknown tool '{name}'"
        try:
            return tool.handler(**arguments)
        except Exception as e:
            logger.warning("Tool '%s' raised", name, exc_info=True)
            return f"Tool error calling '{name}': {e}"
