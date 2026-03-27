from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import PipelineRequest
from .pipeline import EnginePipeline


JSONRPC_VERSION = "2.0"
SUPPORTED_PROTOCOL_VERSIONS = (
    "2024-11-05",
    "2025-03-26",
    "2025-06-18",
    "2025-11-25",
)
LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "mcp_server.log"


def _log(message: str) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message.rstrip()}\n")
    except Exception:
        pass


class McpProtocolError(RuntimeError):
    def __init__(self, code: int, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class McpServer:
    def __init__(self, pipeline: Optional[EnginePipeline] = None) -> None:
        self._pipeline = pipeline
        self.initialized = False
        self.negotiated_protocol_version: Optional[str] = None

    @property
    def pipeline(self) -> EnginePipeline:
        if self._pipeline is None:
            _log("pipeline_init_start")
            self._pipeline = EnginePipeline()
            _log("pipeline_init_done")
        return self._pipeline

    def _server_info(self) -> Dict[str, str]:
        return {"name": "NextMcpServer", "version": "0.1.0"}

    def _tool_definitions(self) -> List[Dict[str, Any]]:
        readonly_annotations = {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        }
        return [
            {
                "name": "ask",
                "description": "Primary final-answer legal Q&A tool using the independent next_mcp engine.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_query": {"type": "string"},
                        "context": {"type": "string"},
                        "request_id": {"type": "string"},
                    },
                    "required": ["user_query"],
                    "additionalProperties": False,
                },
                "annotations": readonly_annotations,
            },
            {
                "name": "answer_with_citations",
                "description": "Preferred final-answer legal Q&A tool returning grounded answer payloads.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_query": {"type": "string"},
                        "context": {"type": "string"},
                        "request_id": {"type": "string"},
                    },
                    "required": ["user_query"],
                    "additionalProperties": False,
                },
                "annotations": readonly_annotations,
            },
            {
                "name": "search_law",
                "description": "Raw law search helper.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "annotations": readonly_annotations,
            },
            {
                "name": "get_article",
                "description": "Raw article fetch helper.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "law_id": {"type": "string"},
                        "article_no": {"type": "string"},
                    },
                    "required": ["law_id", "article_no"],
                    "additionalProperties": False,
                },
                "annotations": readonly_annotations,
            },
            {
                "name": "get_version",
                "description": "Version metadata helper.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"law_id": {"type": "string"}},
                    "required": ["law_id"],
                    "additionalProperties": False,
                },
                "annotations": readonly_annotations,
            },
            {
                "name": "validate_article",
                "description": "Article validation helper.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "law_id": {"type": "string"},
                        "article_no": {"type": "string"},
                    },
                    "required": ["law_id", "article_no"],
                    "additionalProperties": False,
                },
                "annotations": readonly_annotations,
            },
            {
                "name": "search_precedent",
                "description": "Raw precedent search helper.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "annotations": readonly_annotations,
            },
            {
                "name": "get_precedent",
                "description": "Raw precedent detail helper.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"precedent_id": {"type": "string"}},
                    "required": ["precedent_id"],
                    "additionalProperties": False,
                },
                "annotations": readonly_annotations,
            },
        ]

    @staticmethod
    def _jsonrpc_result(request_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
        return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}

    @staticmethod
    def _jsonrpc_error(request_id: Any, code: int, message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            payload["data"] = data
        return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": payload}

    def handle_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(message, dict):
            raise McpProtocolError(-32600, "Invalid Request")

        method = message.get("method")
        params = message.get("params") or {}
        request_id = message.get("id")

        if method == "initialize":
            protocol_version = params.get("protocolVersion")
            if protocol_version not in SUPPORTED_PROTOCOL_VERSIONS:
                protocol_version = SUPPORTED_PROTOCOL_VERSIONS[-1]
            self.initialized = True
            self.negotiated_protocol_version = protocol_version
            return self._jsonrpc_result(
                request_id,
                {
                    "protocolVersion": protocol_version,
                    "capabilities": {"tools": {}, "resources": {}},
                    "serverInfo": self._server_info(),
                },
            )

        if method == "notifications/initialized":
            return None

        if not self.initialized:
            raise McpProtocolError(-32002, "Server not initialized")

        if method == "tools/list":
            return self._jsonrpc_result(request_id, {"tools": self._tool_definitions()})
        if method == "resources/list":
            return self._jsonrpc_result(request_id, {"resources": []})
        if method == "resources/templates/list":
            return self._jsonrpc_result(request_id, {"resourceTemplates": []})
        if method == "tools/call":
            return self._jsonrpc_result(request_id, self._handle_tool_call(params))
        raise McpProtocolError(-32601, "Method not found")

    def _handle_tool_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        _log(f"tools/call name={name}")
        if name in ("ask", "answer_with_citations"):
            user_query = arguments.get("user_query")
            if not isinstance(user_query, str) or not user_query.strip():
                return self._tool_error("missing_user_query")
            return self._safe_tool_call(
                lambda: self._tool_result_from_pipeline(
                    self.pipeline.process(
                        PipelineRequest(
                            user_query=user_query,
                            context=arguments.get("context"),
                            request_id=arguments.get("request_id"),
                        )
                    )
                )
            )
        if name == "search_law":
            query = arguments.get("query")
            if not isinstance(query, str) or not query.strip():
                return self._tool_error("missing_query")
            return self._safe_tool_call(lambda: self._raw_tool_success(self.pipeline.law_gateway.search_law_raw(query)))
        if name == "get_article":
            law_id = arguments.get("law_id")
            article_no = arguments.get("article_no")
            if not law_id:
                return self._tool_error("missing_law_id")
            if not article_no:
                return self._tool_error("missing_article_no")
            return self._safe_tool_call(
                lambda: self._raw_tool_success(self.pipeline.law_gateway.get_article_raw(str(law_id), str(article_no)))
            )
        if name == "get_version":
            law_id = arguments.get("law_id")
            if not law_id:
                return self._tool_error("missing_law_id")
            return self._safe_tool_call(lambda: self._raw_tool_success(self.pipeline.law_gateway.get_version_raw(str(law_id))))
        if name == "validate_article":
            law_id = arguments.get("law_id")
            article_no = arguments.get("article_no")
            if not law_id:
                return self._tool_error("missing_law_id")
            if not article_no:
                return self._tool_error("missing_article_no")
            return self._safe_tool_call(
                lambda: self._raw_tool_success(self.pipeline.law_gateway.validate_article_raw(str(law_id), str(article_no)))
            )
        if name == "search_precedent":
            query = arguments.get("query")
            if not isinstance(query, str) or not query.strip():
                return self._tool_error("missing_query")
            return self._safe_tool_call(
                lambda: self._raw_tool_success(self.pipeline.law_gateway.search_precedent_raw(query))
            )
        if name == "get_precedent":
            precedent_id = arguments.get("precedent_id")
            if not precedent_id:
                return self._tool_error("missing_precedent_id")
            return self._safe_tool_call(
                lambda: self._raw_tool_success(self.pipeline.law_gateway.get_precedent_raw(str(precedent_id)))
            )
        return self._tool_error("unknown_tool")

    def _safe_tool_call(self, runner) -> Dict[str, Any]:
        try:
            return runner()
        except Exception as exc:  # noqa: BLE001
            _log(f"tool_call_error detail={exc}")
            return self._tool_error("backend_error", detail=str(exc))

    def _tool_result_from_pipeline(self, response) -> Dict[str, Any]:
        payload = asdict(response)
        if response.error:
            message = response.error.get("message") or response.error.get("stage") or "pipeline_error"
            _log(f"tool_result_error stage={response.error.get('stage')} message={message}")
            return {
                "content": [{"type": "text", "text": json.dumps({"error": message}, ensure_ascii=False)}],
                "structuredContent": {"error": message, "response": payload},
                "isError": True,
            }
        return {
            "content": [{"type": "text", "text": response.answer}],
            "structuredContent": payload,
            "isError": False,
        }

    @staticmethod
    def _raw_tool_success(payload: Dict[str, Any]) -> Dict[str, Any]:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        return {
            "content": [{"type": "text", "text": text}],
            "structuredContent": payload,
            "isError": False,
        }

    @staticmethod
    def _tool_error(code: str, detail: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"error": code}
        if detail:
            payload["detail"] = detail
        return {
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
            "structuredContent": payload,
            "isError": True,
        }
