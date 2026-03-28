from __future__ import annotations

import time
import unittest

from src.answer_adapter import AnswerAdapter
from src.models import Interpretation, PipelineRequest, RetrievalResult
from tests.fakes import FakeLawGateway


class AnswerAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gateway = FakeLawGateway()
        self.privacy_law = self.gateway.resolve_law_family("개인정보 보호법")

    def _sanction_article(self, article_no: str, match_label: str, matched_text: str, penalty_summary: str):
        article = self.gateway.get_article(self.privacy_law, article_no)
        return {
            **article,
            "sanction_type": "벌칙" if article_no == "제71조" else "과태료",
            "matched_clauses": [
                {
                    "match_label": match_label,
                    "matched_text": matched_text,
                    "penalty_summary": penalty_summary,
                }
            ],
            "penalty_summary": penalty_summary,
        }

    def test_visible_sanctions_are_synchronized_across_outputs(self):
        article = self.gateway.get_article(self.privacy_law, "제17조")
        sanction = self._sanction_article(
            "제71조",
            "제71조 제1호",
            "제17조제1항제1호를 위반하여 정보주체의 동의를 받지 아니하고 개인정보를 제3자에게 제공한 자",
            "5년 이하의 징역 또는 5천만원 이하의 벌금에 처한다.",
        )
        retrieval = RetrievalResult(
            interpretation=Interpretation(
                intent="illegality",
                query_mode="single_basis",
                privacy_categories=["제재/책임"],
                issue_terms=["제3자제공"],
            ),
            primary_law=self.privacy_law,
            article=article,
            related_articles=[],
            framework_axes=[],
            used_search_query=self.privacy_law.law_name,
            search_queries=[self.privacy_law.law_name],
            related_law_queries=[],
            version=None,
            precedent=None,
            sanction_articles=[sanction],
        )

        response = AnswerAdapter().compose(
            request=PipelineRequest(user_query="동의 없이 개인정보를 제3자에게 제공하면 처벌받나?"),
            retrieval=retrieval,
            started_at=time.time(),
        )

        self.assertIn("[제재 참고]", response.answer)
        self.assertIn("제71조 제1호", response.answer)
        self.assertIn("5년 이하의 징역 또는 5천만원 이하의 벌금에 처한다.", response.answer)
        self.assertEqual(response.citations["law_context"]["sanction_articles"], [sanction])
        self.assertEqual(response.answer_plan["sanction_reference"], [sanction])
        checkpoints = response.answer_plan["privacy_analysis"]["legal_basis_checkpoints"]
        self.assertIn("개인정보 보호법 제71조", checkpoints)

    def test_hidden_sanctions_are_filtered_from_all_outputs(self):
        article = self.gateway.get_article(self.privacy_law, "제17조")
        sanction = self._sanction_article(
            "제71조",
            "제71조 제1호",
            "제17조제1항제1호를 위반하여 정보주체의 동의를 받지 아니하고 개인정보를 제3자에게 제공한 자",
            "5년 이하의 징역 또는 5천만원 이하의 벌금에 처한다.",
        )
        retrieval = RetrievalResult(
            interpretation=Interpretation(
                intent="requirements",
                query_mode="single_basis",
                privacy_categories=["처리 근거"],
                issue_terms=["제3자제공"],
            ),
            primary_law=self.privacy_law,
            article=article,
            related_articles=[],
            framework_axes=[],
            used_search_query=self.privacy_law.law_name,
            search_queries=[self.privacy_law.law_name],
            related_law_queries=[],
            version=None,
            precedent=None,
            sanction_articles=[sanction],
        )

        response = AnswerAdapter().compose(
            request=PipelineRequest(user_query="동의 없이 개인정보를 제3자에게 제공하면 어떤 조문이야?"),
            retrieval=retrieval,
            started_at=time.time(),
        )

        self.assertNotIn("[제재 참고]", response.answer)
        self.assertEqual(response.citations["law_context"]["sanction_articles"], [])
        self.assertEqual(response.answer_plan["sanction_reference"], [])
        checkpoints = response.answer_plan["privacy_analysis"]["legal_basis_checkpoints"]
        self.assertNotIn("개인정보 보호법 제71조", checkpoints)


if __name__ == "__main__":
    unittest.main()
