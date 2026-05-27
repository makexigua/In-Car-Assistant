"""
MCP 客户端 — transport 层。

行业实践：
  - 纯传输层，不掺入业务逻辑
  - 内置健康检查 (health_check)
  - 调用级超时 (call_tool timeout)
  - 断线重连 (reconnect)
  - 异常向上抛，由上层决定重试或熔断
"""

import asyncio
import os
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from main.utils import logger


class MCPClient:
    """长连接 MCP 客户端（transport 层）。"""

    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.session: Optional[ClientSession] = None
        self._connected = False
        self._server_params: Optional[StdioServerParameters] = None

    # ---- 状态 ----

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ---- 连接 / 断开 ----

    async def connect(
        self,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
    ) -> List[Any]:
        """连接 MCP 服务器，返回工具列表。

        Args:
            command: 启动命令
            args: 命令参数
            env: 环境变量
            timeout: 整体连接超时（秒）
        """
        merged_env = os.environ.copy()
        if env:
            merged_env.update({k: v for k, v in env.items() if v})

        self._server_params = StdioServerParameters(
            command=command,
            args=args or [],
            env=merged_env,
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(self._server_params)
        )
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )

        await asyncio.wait_for(self.session.initialize(), timeout=timeout)
        self._connected = True

        response = await self.session.list_tools()
        logger.info(
            "MCP 已连接，可用工具: %s",
            [t.name for t in response.tools],
        )
        return response.tools

    async def disconnect(self) -> None:
        """断开连接，释放资源。"""
        self._connected = False
        await self.exit_stack.aclose()

    async def reconnect(
        self,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
    ) -> bool:
        """断线重连。"""
        try:
            await self.disconnect()
            self.exit_stack = AsyncExitStack()
            await self.connect(command, args, env, timeout=timeout)
            return True
        except Exception as err:
            logger.error("[MCP] 重连失败: %s", err)
            return False

    # ---- 健康检查 ----

    async def health_check(self) -> bool:
        """轻量健康检查，用 list_tools 探测。"""
        if not self._connected or not self.session:
            return False
        try:
            await asyncio.wait_for(self.session.list_tools(), timeout=5.0)
            return True
        except Exception:
            return False

    # ---- 工具调用 ----

    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Any:
        """调用 MCP 工具，支持超时。

        Raises:
            RuntimeError: 未连接
            asyncio.TimeoutError: 超时
            Exception: 调用异常
        """
        if not self._connected or not self.session:
            raise RuntimeError("MCP 未连接，请先调用 connect()")
        return await asyncio.wait_for(
            self.session.call_tool(name, arguments),
            timeout=timeout,
        )

    # ---- 结果解析 ----

    @staticmethod
    def extract_text(result: Any) -> str:
        """从 CallToolResult 中提取文本内容。"""
        try:
            content = getattr(result, "content", None) or []
            if not content:
                return str(result)
            first = content[0]
            text = getattr(first, "text", None)
            return str(text) if text is not None else str(first)
        except Exception:
            return str(result)
