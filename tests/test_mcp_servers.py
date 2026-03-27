from __future__ import annotations

import io
import json
import unittest

from src.mcp_core import McpServer
from src.mcp_http_server import dispatch_http_payload, is_authorized_request, parse_jsonrpc_http_body
from src.mcp_stdio_server import _read_message, _write_message
from src.models import PipelineResponse


class FakeLawGateway:
    def search_law_raw(self, query):
        return {"LawSearch": {"law": [{"법령ID": "011357", "법령명한글": "개인정보 보호법"}], "query": query}}

    def get_article_raw(self, law_id, article_no):
        return {"law_id": law_id, "article_no": article_no, "found": True, "article_text": "제15조 본문"}

    def get_version_raw(self, law_id):
        return {"law_id": law_id, "version_fields": {"시행일자": "20251002"}}

    def validate_article_raw(self, law_id, article_no):
        return {"law_id": law_id, "article_no": article_no, "is_valid": True}

    def search_precedent_raw(self, query):
        return {"PrecSearch": {"prec": [{"판례일련번호": "123", "사건명": "개인정보 사건", "사건번호": "2025다12345"}]}}

    def get_precedent_raw(self, precedent_id):
        return {"precedent_id": precedent_id, "사건명": "개인정보 사건", "사건번호": "2025다12345"}


class FakePipeline:
    def __init__(self):
        self.law_gateway = FakeLawGateway()

    def process(self, req):
        return PipelineResponse(
            request_id=req.request_id or "req-1",
            risk_level="LOW",
            mode="single_agent",
            answer="테스트 응답",
            citations={"law_context": {"primary_law": {"law_name": "개인정보 보호법"}, "article": {"article_no": "제15조"}}},
            score=90.0,
            latency_ms=1.0,
            error=None,
        )


class McpServerContractTests(unittest.TestCase):
    def setUp(self):
        self.server = McpServer(pipeline=FakePipeline())

    def _initialize(self):
        return self.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}},
            }
        )

    def test_tools_list_contains_expected_tools(self):
        self._initialize()
        result = self.server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tool_names = [tool["name"] for tool in result["result"]["tools"]]
        self.assertIn("ask", tool_names)
        self.assertIn("answer_with_citations", tool_names)
        self.assertIn("get_article", tool_names)

    def test_ask_returns_pipeline_payload(self):
        self._initialize()
        result = self.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "ask", "arguments": {"user_query": "개인정보 수집 조문이 뭐야?"}},
            }
        )
        self.assertFalse(result["result"]["isError"])
        self.assertEqual(result["result"]["structuredContent"]["answer"], "테스트 응답")

    def test_http_dispatch_and_stdio_roundtrip(self):
        payload = parse_jsonrpc_http_body(
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, ensure_ascii=False).encode("utf-8")
        )
        self.assertEqual(payload["method"], "tools/list")

        init = dispatch_http_payload(
            self.server,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}},
            },
        )
        self.assertEqual(init["result"]["protocolVersion"], "2025-03-26")

        buffer = io.BytesIO()
        _write_message(buffer, {"jsonrpc": "2.0", "id": 99, "method": "ping"})
        buffer.seek(0)
        roundtrip = _read_message(buffer)
        self.assertEqual(roundtrip["method"], "ping")

    def test_auth_helper(self):
        self.assertTrue(is_authorized_request({}))
        self.assertTrue(is_authorized_request({"Authorization": "Bearer token"}, expected_token="token"))
        self.assertFalse(is_authorized_request({"Authorization": "Bearer wrong"}, expected_token="token"))


if __name__ == "__main__":
    unittest.main()
