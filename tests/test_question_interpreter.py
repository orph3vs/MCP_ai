from __future__ import annotations

import unittest

from src.models import PipelineRequest
from src.ollama_client import OllamaClient
from src.question_interpreter import QuestionInterpreter


class QuestionInterpreterTests(unittest.TestCase):
    def test_ollama_payload_is_used_when_schema_is_valid(self):
        def transport(_endpoint, _payload, _timeout):
            return {
                "response": (
                    '{"intent":"applicability","query_mode":"single_basis","explicit_law_families":["개인정보 보호법"],'
                    '"candidate_law_families":["개인정보 보호법"],"issue_terms":["수집이용"],'
                    '"privacy_categories":["처리 근거"],'
                    '"candidate_direct_basis_articles":[{"law_family":"개인정보 보호법","article_no":"제15조","reason":"ai"}],'
                    '"needs_clarification":false,"clarification_points":[]}'
                )
            }

        interpreter = QuestionInterpreter(OllamaClient(transport=transport))
        result = interpreter.interpret(PipelineRequest(user_query="개인정보 수집 조문이 뭐야?"))

        self.assertEqual(result.routing_source, "ollama")
        self.assertEqual(result.intent, "applicability")
        self.assertEqual(result.candidate_direct_basis_articles[0].article_no, "제15조")

    def test_rules_fallback_runs_when_ollama_payload_is_invalid(self):
        def transport(_endpoint, _payload, _timeout):
            return {"response": '{"intent":"unknown"}'}

        interpreter = QuestionInterpreter(OllamaClient(transport=transport))
        result = interpreter.interpret(PipelineRequest(user_query="개인정보 수집 조문이 뭐야?"))

        self.assertEqual(result.routing_source, "rules_fallback")
        self.assertEqual(result.candidate_direct_basis_articles[0].article_no, "제15조")

    def test_transport_error_is_kept_in_diagnostics(self):
        def transport(_endpoint, _payload, _timeout):
            raise RuntimeError("ollama_http_error status=500 detail=model requires more system memory")

        interpreter = QuestionInterpreter(OllamaClient(transport=transport))
        result = interpreter.interpret(PipelineRequest(user_query="개인정보 수집 조문이 뭐야?"))

        self.assertEqual(result.routing_source, "rules_fallback")
        self.assertIn("more system memory", result.diagnostics[0])

    def test_generic_use_query_without_privacy_context_does_not_map_to_privacy_basis(self):
        def transport(_endpoint, _payload, _timeout):
            raise RuntimeError("forced fallback")

        interpreter = QuestionInterpreter(OllamaClient(transport=transport))
        result = interpreter.interpret(PipelineRequest(user_query="서비스 이용약관은 어디서 봐?"))

        self.assertEqual(result.routing_source, "rules_fallback")
        self.assertEqual(result.candidate_law_families, [])
        self.assertEqual(result.privacy_categories, [])
        self.assertEqual(result.candidate_direct_basis_articles, [])

    def test_service_withdrawal_query_does_not_trigger_privacy_rights(self):
        def transport(_endpoint, _payload, _timeout):
            raise RuntimeError("forced fallback")

        interpreter = QuestionInterpreter(OllamaClient(transport=transport))
        result = interpreter.interpret(PipelineRequest(user_query="서비스 탈퇴 방법이 뭐야?"))

        self.assertEqual(result.routing_source, "rules_fallback")
        self.assertEqual(result.candidate_law_families, [])
        self.assertEqual(result.privacy_categories, [])


if __name__ == "__main__":
    unittest.main()
