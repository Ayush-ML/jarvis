# This Script is responsible for connecting to configured MCP servers and exposing whatever
# tools they provide into the agent's context -- i.e. building the list that gets merged into
# OpenAIRequestSchema.tools, and dispatching the model's tool_calls back out to the right server.
#
# Built on mcp.ClientSessionGroup (not the plain mcp.Client), since this needs to hold MULTIPLE
# server connections at once with automatic name-collision handling -- ClientSessionGroup is the
# SDK's own abstraction for exactly that (see https://py.sdk.modelcontextprotocol.io/client/session-groups/).
#
# ASYNC/SYNC BRIDGE: the MCP SDK is asyncio-native, but the rest of the "brain" layer (ModelClient,
# ConversationService) is synchronous. Re-opening connections per call would mean respawning stdio
# subprocess servers on every single tool call, which is both slow and wasteful -- so this runs a
# persistent background event loop for the app's whole lifetime, and synchronous callers reach into
# it via asyncio.run_coroutine_threadsafe(). Same reasoning as why Transcriber/Database/VectorStore
# are constructed once and reused, just with a thread+loop instead of a plain object.
#
# A REAL API GOTCHA WORTH KNOWING: unlike the plain mcp.Client (which turns an unknown tool name
# into a graceful is_error=True result), ClientSessionGroup.call_tool() does
# `session = self._tool_to_session[name]` with no guard at all -- an unrecognized name raises a
# bare KeyError, not a friendly error. Confirmed by reading the actual SDK source, not assumed by
# analogy with the other class. call_tool() below checks membership before calling specifically
# because of this.
#
# ELICITATION (mid-call "I need more input", 2026-07-28 spec): a tool can return InputRequiredResult
# instead of finishing, carrying input_requests (a dict of questions) and an opaque request_state
# token. The client answers the questions and retries with input_responses + request_state attached.
# The high-level mcp.Client class has a BUILT-IN loop for this ("Client drives that loop for you",
# per the SDK's own v2 docs) -- but that convenience lives specifically on Client.call_tool(), and
# ClientSessionGroup.call_tool() (source read directly, not assumed) is a thin pass-through to the
# low-level session with no such loop. So this hand-rolls the same loop the SDK's own docs show
# doing manually via client.session.call_tool() -- structurally identical, just against the group.
#
# input_requests is a union of request types; ElicitRequest ("ask the human a direct question") is
# the one handled here, since it's the practically relevant case for local tool servers and its
# request/response shape is verified from actual SDK examples. Sampling (CreateMessageRequest) and
# roots-list (ListRootsRequest) requests fail the call cleanly instead of guessing at response
# shapes I haven't verified -- a wrong guess sent back over the wire is worse than an honest error.
import asyncio
import json
import logging
import threading
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from mcp import ClientSessionGroup, StdioServerParameters, MCPError
from mcp.client.session_group import StreamableHttpParameters, SseServerParameters
from mcp.types import (
    Implementation, TextContent,
    InputRequiredResult, InputResponse,
    ElicitRequest, ElicitResult,
)

from src.core.config import MCP_CONFIG_PATH, MCP_CONNECT_TIMEOUT_SECONDS, MCP_MAX_INPUT_REQUIRED_ROUNDS

logger = logging.getLogger(__name__)

ElicitHandler = Callable[[ElicitRequest], Awaitable[ElicitResult]]


def _namespaced_name(name: str, server_info: Implementation) -> str:
    """
    Prefixes every tool/resource/prompt name with its server's name, so two
    independently-authored servers can't collide on a name like 'search'.
    '__' rather than the SDK docs' '.' example -- OpenAI-compatible tool
    names commonly disallow dots; underscore is safe everywhere.
    """
    return f"{server_info.name}__{name}"


class MCPRegistry:
    """
    Owns a persistent background event loop and a ClientSessionGroup connected
    to every server in MCP_CONFIG_PATH for the app's whole lifetime. Construct
    ONCE; call start() before use (blocks until connected), stop() at shutdown.
    """

    def __init__(
        self,
        config_path: str = MCP_CONFIG_PATH,
        elicit_handler: Optional[ElicitHandler] = None,
    ) -> None:
        self._config_path = config_path
        self._elicit_handler = elicit_handler  # None -> declines cleanly rather than fabricating an answer, same default the SDK itself uses
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._group: Optional[ClientSessionGroup] = None
        self._ready = threading.Event()

    def start(self) -> None:
        """Spins up the background loop and connects to every configured server. Blocks until ready."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._ready.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        # _run_loop always sets this event, including when initialization fails.
        self._ready.wait(timeout=MCP_CONNECT_TIMEOUT_SECONDS + 5)
        if not self._ready.is_set():
            raise RuntimeError("Timed out while starting the MCP registry")

    def stop(self) -> None:
        loop = self._loop
        if loop is None or not loop.is_running():
            return
        try:
            asyncio.run_coroutine_threadsafe(self._disconnect_all(), loop).result(timeout=10)
        except Exception:
            logger.warning("Error disconnecting MCP servers", exc_info=True)
        loop.call_soon_threadsafe(loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._loop = None
        self._thread = None
        self._group = None

    def list_openai_tools(self) -> List[Dict[str, Any]]:
        """Converts every connected server's tools into the OpenAI tool-calling schema, ready to merge into OpenAIRequestSchema.tools."""
        if self._group is None:
            return []
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description or "",
                    "parameters": tool.input_schema,
                },
            }
            for name, tool in self._group.tools.items()
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Synchronous entry point for the (synchronous) tool-dispatch loop --
        runs the actual async call on the background loop and blocks this
        calling thread until it completes. Returns plain text suitable for a
        role: "tool" message's content -- never raises; failures come back
        as a "Tool error: ..." string so a bad tool call can't crash a turn.
        """
        if self._loop is None or not self._loop.is_running():
            return "Tool error: MCP registry has not been started."
        future = asyncio.run_coroutine_threadsafe(self._call_tool_async(name, arguments), self._loop)
        try:
            return future.result()
        except Exception as exc:
            logger.warning("Unexpected MCP tool-call failure for '%s'", name, exc_info=True)
            return f"Tool error calling '{name}': {exc}"

    # -- internals, all run on the background loop's thread --

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_all())
        except Exception:
            logger.warning("Failed to initialize the MCP registry", exc_info=True)
            self._ready.set()
            self._loop.close()
            return
        self._ready.set()
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()

    async def _connect_all(self) -> None:
        group = ClientSessionGroup(component_name_hook=_namespaced_name)
        self._group = group
        await group.__aenter__()
        for name, params in self._load_config().items():
            try:
                await asyncio.wait_for(
                    group.connect_to_server(params),
                    timeout=MCP_CONNECT_TIMEOUT_SECONDS,
                )
            except Exception:
                # One misconfigured or offline server shouldn't take down every other one --
                # log it and keep going, same philosophy as ConversationService's indexing failures.
                logger.warning("Failed to connect to MCP server '%s'", name, exc_info=True)

    async def _disconnect_all(self) -> None:
        if self._group is not None:
            await self._group.__aexit__(None, None, None)

    async def _call_tool_async(self, name: str, arguments: Dict[str, Any]) -> str:
        if self._group is None or name not in self._group.tools:
            return f"Tool error: unknown tool '{name}'"

        try:
            result = await self._group.call_tool(name, arguments, allow_input_required=True)
        except MCPError as e:
            return f"Tool error calling '{name}': {e}"
        except Exception as e:
            logger.warning("Unexpected error calling MCP tool '%s'", name, exc_info=True)
            return f"Tool error calling '{name}': {e}"

        rounds = 0
        while isinstance(result, InputRequiredResult):
            rounds += 1
            if rounds > MCP_MAX_INPUT_REQUIRED_ROUNDS:
                return (f"Tool error: '{name}' asked for input more than "
                        f"{MCP_MAX_INPUT_REQUIRED_ROUNDS} times in a row -- aborting rather than looping forever.")

            responses: Dict[str, InputResponse] = {}
            for key, request in (result.input_requests or {}).items():
                if not isinstance(request, ElicitRequest):
                    kind = type(request).__name__
                    return f"Tool error: '{name}' needs a '{kind}' request answered, which isn't supported yet."
                responses[key] = await self._answer_elicitation(request)

            try:
                result = await self._group.call_tool(
                    name, arguments,
                    input_responses=responses,
                    request_state=result.request_state,
                    allow_input_required=True,
                )
            except MCPError as e:
                return f"Tool error calling '{name}': {e}"
            except Exception as e:
                logger.warning("Unexpected error calling MCP tool '%s'", name, exc_info=True)
                return f"Tool error calling '{name}': {e}"

        text_parts = [block.text for block in result.content if isinstance(block, TextContent)]
        text = "\n".join(text_parts) if text_parts else str(result.structured_content)
        return f"Tool error: {text}" if result.is_error else text

    async def _answer_elicitation(self, request: ElicitRequest) -> ElicitResult:
        if self._elicit_handler is None:
            return ElicitResult(action="decline")
        try:
            return await self._elicit_handler(request)
        except Exception:
            logger.warning("elicit_handler raised while answering an elicitation request", exc_info=True)
            return ElicitResult(action="decline")

    def _load_config(self) -> Dict[str, Any]:
        path = Path(self._config_path)
        if not path.exists():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))

        servers: Dict[str, Any] = {}
        for name, entry in raw.get("mcpServers", {}).items():
            transport = entry.get("transport", "stdio")
            if transport == "stdio":
                servers[name] = StdioServerParameters(
                    command=entry["command"],
                    args=entry.get("args", []),
                    env=entry.get("env"),
                )
            elif transport == "http":
                servers[name] = StreamableHttpParameters(url=entry["url"])
            elif transport == "sse":
                servers[name] = SseServerParameters(url=entry["url"])
            else:
                logger.warning("Unknown MCP transport '%s' for server '%s', skipping", transport, name)
        return servers
