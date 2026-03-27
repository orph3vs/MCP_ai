from __future__ import annotations

import unittest
from pathlib import Path

from src.models import PipelineRequest
from src.ollama_client import OllamaClient
from src.pipeline import EnginePipeline
from src.policy_engine import PolicyEngine
from src.question_interpreter import QuestionInterpreter
from tests.fakes import FakeLawGateway


class PipelineTests(unittest.TestCase):
    def _pipeline(self) -> EnginePipeline:
        def broken_transport(_endpoint, _payload, _timeout):
            raise ValueError("ollama unavailable")

        config_dir = Path(__file__).resolve().parents[1] / "config"
        return EnginePipeline(
            law_gateway=FakeLawGateway(),
            interpreter=QuestionInterpreter(OllamaClient(transport=broken_transport)),
            policy_engine=PolicyEngine(config_dir=config_dir),
        )

    def test_privacy_collection_maps_to_article_15(self):
        response = self._pipeline().process(PipelineRequest(user_query="개보법에서 개인정보 수집과 관련된 조문이 어떤거지?"))
        self.assertEqual(response.answer_plan["direct_basis"]["article_no"], "제15조")

    def test_third_party_provision_maps_to_article_17(self):
        response = self._pipeline().process(PipelineRequest(user_query="개인정보 제3자 제공은 어떤 조문을 보면 되나?"))
        self.assertEqual(response.answer_plan["direct_basis"]["article_no"], "제17조")

    def test_entrustment_maps_to_article_26(self):
        response = self._pipeline().process(PipelineRequest(user_query="개인정보 위탁은 어떤 조문을 보면 되나?"))
        self.assertEqual(response.answer_plan["direct_basis"]["article_no"], "제26조")

    def test_cctv_incident_prioritizes_article_58(self):
        response = self._pipeline().process(
            PipelineRequest(user_query="자연재해나 인적실수로 인해 cctv영상이 소실 삭제 되었다면 통지 대상인가?")
        )
        self.assertEqual(response.answer_plan["direct_basis"]["article_no"], "제58조")
        related = [item["article_no"] for item in response.citations["law_context"]["related_articles"]]
        self.assertIn("제25조", related)
        self.assertIn("제34조", related)

    def test_ad_transmission_maps_to_network_act_article_50(self):
        response = self._pipeline().process(PipelineRequest(user_query="문자 광고 수신거부 후 계속 보내면 위반이야?"))
        self.assertEqual(response.answer_plan["direct_basis"]["article_no"], "제50조")
        self.assertEqual(response.answer_plan["direct_basis"]["law_name"], "정보통신망 이용촉진 및 정보보호 등에 관한 법률")

    def test_version_lookup_failure_does_not_fail_pipeline(self):
        class VersionFailingLawGateway(FakeLawGateway):
            def get_version(self, law):
                raise RuntimeError("version lookup failed")

        def broken_transport(_endpoint, _payload, _timeout):
            raise ValueError("ollama unavailable")

        config_dir = Path(__file__).resolve().parents[1] / "config"
        pipeline = EnginePipeline(
            law_gateway=VersionFailingLawGateway(),
            interpreter=QuestionInterpreter(OllamaClient(transport=broken_transport)),
            policy_engine=PolicyEngine(config_dir=config_dir),
        )

        response = pipeline.process(PipelineRequest(user_query="개보법에서 개인정보 수집과 관련된 조문이 어떤거지?"))

        self.assertIsNone(response.error)
        self.assertEqual(response.answer_plan["direct_basis"]["article_no"], "제15조")
        self.assertIsNone(response.citations["law_context"]["version"])

    def test_cctv_deletion_request_does_not_trigger_article_58_exception(self):
        response = self._pipeline().process(PipelineRequest(user_query="cctv 영상 삭제 요청은 어떤 조문을 보면 되나?"))

        self.assertEqual(response.answer_plan["direct_basis"]["article_no"], "제36조")


if __name__ == "__main__":
    unittest.main()
