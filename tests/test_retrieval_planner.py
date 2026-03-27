from __future__ import annotations

import unittest

from src.models import DirectBasisCandidate, Interpretation
from src.retrieval_planner import RetrievalPlanner
from tests.fakes import FakeLawGateway


class RetrievalPlannerTests(unittest.TestCase):
    def test_unresolved_direct_basis_candidate_does_not_fall_back_to_primary_law_article(self):
        interpretation = Interpretation(
            intent="requirements",
            query_mode="single_basis",
            candidate_law_families=["개인정보 보호법"],
            candidate_direct_basis_articles=[DirectBasisCandidate("해결되지 않은 법령", "제15조", "test")],
        )

        result = RetrievalPlanner(FakeLawGateway()).plan(interpretation, "테스트")

        self.assertEqual(result.primary_law.law_name, "개인정보 보호법")
        self.assertIsNone(result.article)

    def test_planner_uses_injected_privacy_sanction_resolver(self):
        class StubSanctionResolver:
            def __init__(self) -> None:
                self.called_with = None

            def resolve(self, **kwargs):
                self.called_with = kwargs
                return [{"article_no": "제75조", "matched_clauses": []}]

        resolver = StubSanctionResolver()
        planner = RetrievalPlanner(FakeLawGateway(), sanction_resolver=resolver)
        interpretation = Interpretation(
            intent="illegality",
            query_mode="single_basis",
            candidate_law_families=["개인정보 보호법"],
            candidate_direct_basis_articles=[DirectBasisCandidate("개인정보 보호법", "제26조", "test")],
        )

        result = planner.plan(interpretation, "개인정보 처리위탁 계약서를 문서로 하지 않으면 과태료가 있나?")

        self.assertEqual(result.sanction_articles, [{"article_no": "제75조", "matched_clauses": []}])
        self.assertIsNotNone(resolver.called_with)
        self.assertEqual(resolver.called_with["user_query"], "개인정보 처리위탁 계약서를 문서로 하지 않으면 과태료가 있나?")
        self.assertEqual(resolver.called_with["article"]["article_no"], "제26조")


if __name__ == "__main__":
    unittest.main()
