from __future__ import annotations

import unittest
from pathlib import Path

from src.models import PipelineRequest
from src.ollama_client import OllamaClient
from src.pipeline import EnginePipeline
from src.policy_engine import PolicyEngine
from src.question_interpreter import QuestionInterpreter
from tests.fakes import FakeLawGateway


class OfflineBenchmarkTests(unittest.TestCase):
    def _pipeline(self) -> EnginePipeline:
        def broken_transport(_endpoint, _payload, _timeout):
            raise RuntimeError("offline benchmark forces rules fallback")

        config_dir = Path(__file__).resolve().parents[1] / "config"
        return EnginePipeline(
            law_gateway=FakeLawGateway(),
            interpreter=QuestionInterpreter(OllamaClient(transport=broken_transport)),
            policy_engine=PolicyEngine(config_dir=config_dir),
        )

    def test_representative_offline_questions(self):
        cases = [
            {
                "query": "개보법에서 개인정보 수집과 관련된 조문이 어떤거지?",
                "article_no": "제15조",
                "law_name": "개인정보 보호법",
                "query_mode": "single_basis",
                "sanction_visible": False,
            },
            {
                "query": "개인정보 제3자 제공은 어떤 조문을 보면 되나?",
                "article_no": "제17조",
                "law_name": "개인정보 보호법",
                "query_mode": "single_basis",
                "sanction_visible": False,
            },
            {
                "query": "개인정보 위탁은 어떤 조문을 보면 되나?",
                "article_no": "제26조",
                "law_name": "개인정보 보호법",
                "query_mode": "single_basis",
                "sanction_visible": False,
            },
            {
                "query": "cctv 영상 삭제 요청은 어떤 조문을 보면 되나?",
                "article_no": "제36조",
                "law_name": "개인정보 보호법",
                "query_mode": "single_basis",
                "sanction_visible": False,
            },
            {
                "query": "자연재해나 인적실수로 인해 cctv영상이 소실 삭제 되었다면 통지 대상인가?",
                "article_no": "제58조",
                "law_name": "개인정보 보호법",
                "query_mode": "single_basis",
                "sanction_visible": False,
            },
            {
                "query": "문자 광고 수신거부 후 계속 보내면 위반이야?",
                "article_no": "제50조",
                "law_name": "정보통신망 이용촉진 및 정보보호 등에 관한 법률",
                "query_mode": "single_basis",
                "sanction_visible": False,
            },
            {
                "query": "동의 없이 개인정보를 제3자에게 제공하면 어떤 조문이야?",
                "article_no": "제17조",
                "law_name": "개인정보 보호법",
                "query_mode": "single_basis",
                "sanction_visible": False,
            },
            {
                "query": "동의 없이 개인정보를 제3자에게 제공하면 처벌받나?",
                "article_no": "제17조",
                "law_name": "개인정보 보호법",
                "query_mode": "single_basis",
                "sanction_visible": True,
                "sanction_article_no": "제71조",
            },
            {
                "query": "개인정보 처리위탁 계약서를 문서로 하지 않으면 과태료가 있나?",
                "article_no": "제26조",
                "law_name": "개인정보 보호법",
                "query_mode": "single_basis",
                "sanction_visible": True,
                "sanction_article_no": "제75조",
            },
            {
                "query": "광고 문자 발송 관련 법 체계를 정리해줘",
                "article_no": None,
                "law_name": None,
                "query_mode": "framework_overview",
                "framework_axes_min": 2,
                "sanction_visible": False,
            },
            {
                "query": "서비스 탈퇴 방법이 뭐야?",
                "article_no": None,
                "law_name": None,
                "query_mode": "single_basis",
                "sanction_visible": False,
                "privacy_categories": [],
            },
        ]

        pipeline = self._pipeline()
        for case in cases:
            with self.subTest(query=case["query"]):
                response = pipeline.process(PipelineRequest(user_query=case["query"]))

                self.assertIsNone(response.error)
                self.assertEqual(response.citations["law_context"]["routing_source"], "rules_fallback")
                self.assertEqual(response.answer_plan["query_mode"], case["query_mode"])

                direct_basis = response.answer_plan["direct_basis"]
                if case["article_no"] is None:
                    self.assertIsNone(direct_basis)
                else:
                    self.assertIsNotNone(direct_basis)
                    self.assertEqual(direct_basis["article_no"], case["article_no"])
                    self.assertEqual(direct_basis["law_name"], case["law_name"])

                if "framework_axes_min" in case:
                    self.assertGreaterEqual(
                        len(response.citations["law_context"]["framework_axes"]),
                        case["framework_axes_min"],
                    )

                expected_categories = case.get("privacy_categories")
                if expected_categories is not None:
                    self.assertEqual(response.answer_plan["privacy_categories"], expected_categories)

                if case["sanction_visible"]:
                    self.assertIn("[제재 참고]", response.answer)
                    self.assertTrue(response.answer_plan["sanction_reference"])
                    self.assertTrue(response.citations["law_context"]["sanction_articles"])
                    self.assertEqual(
                        response.answer_plan["sanction_reference"][0]["article_no"],
                        case["sanction_article_no"],
                    )
                    self.assertEqual(
                        response.citations["law_context"]["sanction_articles"][0]["article_no"],
                        case["sanction_article_no"],
                    )
                else:
                    self.assertNotIn("[제재 참고]", response.answer)
                    self.assertEqual(response.answer_plan["sanction_reference"], [])
                    self.assertEqual(response.citations["law_context"]["sanction_articles"], [])


if __name__ == "__main__":
    unittest.main()
