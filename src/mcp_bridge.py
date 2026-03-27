from __future__ import annotations

from .mcp_core import McpServer
from .pipeline import EnginePipeline


def build_pipeline() -> EnginePipeline:
    return EnginePipeline()


def build_server() -> McpServer:
    return McpServer(pipeline=build_pipeline())
