# 作用：封装远端 MCP 客户端连接与工具调用，供 task 执行阶段复用。

import asyncio
import os
import sys
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    def __init__(self):
        """初始化 MCP 客户端。"""
        self.exit_stack = AsyncExitStack()
        self.session: Optional[ClientSession] = None

    def _build_server_params(
        self,
        server_script_path: Optional[str] = None,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> StdioServerParameters:
        """
        统一构建 MCP server 启动参数。
        - 传 command/args：走命令式启动（适配 npx 官方 MCP server）。
        - 仅传 server_script_path：保留脚本模式兼容能力。
        """
        if command:
            merged_env = os.environ.copy()
            if env:
                # 过滤空值，避免把空字符串覆盖系统环境变量。
                merged_env.update({key: value for key, value in env.items() if value})
            return StdioServerParameters(
                command=command,
                args=args or [],
                env=merged_env,
            )

        if not server_script_path:
            raise ValueError("未提供 MCP server 启动参数，请传 command 或 server_script_path")

        is_python = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
        if not (is_python or is_js):
            raise ValueError("服务器脚本必须是 .py 或 .js 文件")

        script_command = sys.executable if is_python else "node"
        return StdioServerParameters(
            command=script_command,
            args=[server_script_path],
            env=None,
        )

    async def connect_to_server(
        self,
        server_script_path: Optional[str] = None,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        """连接到 MCP 服务器并列出可用工具。"""
        server_params = self._build_server_params(
            server_script_path=server_script_path,
            command=command,
            args=args,
            env=env,
        )

        # 启动 MCP 服务器并建立通信
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # 列出 MCP 服务器上的工具
        response = await self.session.list_tools()
        tools = response.tools
        print("\n已连接到服务器，支持以下工具:", [tool.name for tool in tools])

    @staticmethod
    def _extract_result_text(result: Any) -> str:
        """
        优先提取第一段 text 内容；没有 text 时返回 str(result)，
        这样调用方至少能拿到可读信息用于排障。
        """
        try:
            content = getattr(result, "content", None) or []
            if not content:
                return str(result)
            first = content[0]
            text = getattr(first, "text", None)
            return str(text) if text is not None else str(first)
        except Exception:
            return str(result)

    async def execute(self, function_name, tool_args):
        print("\n🤖 MCP 客户端已启动")

        try:
            # 执行工具
            result = await self.session.call_tool(function_name, tool_args)
            print(f"\n\n[Calling tool with args {tool_args}]\n\n")
            result_text = self._extract_result_text(result)
            print(f"\n🤖 MCP Response: {result_text}")
            return result_text

        except Exception as err:
            print(f"\n⚠️ 发生错误: {str(err)}")
            return "Not Find"

    async def cleanup(self):
        """清理资源。"""
        await self.exit_stack.aclose()


async def main():
    client = MCPClient()
    try:
        await client.connect_to_server(
            command="npx",
            args=["-y", "@amap/amap-maps-mcp-server"],
            env={"AMAP_MAPS_API_KEY": os.getenv("AMAP_MAPS_API_KEY", "")},
        )
        await client.execute("maps_weather", {"city": "北京", "date": "2026-05-21"})
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
