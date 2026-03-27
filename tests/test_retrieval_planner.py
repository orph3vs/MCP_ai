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


if __name__ == "__main__":
    unittest.main()
