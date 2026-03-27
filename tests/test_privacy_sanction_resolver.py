from __future__ import annotations

import unittest

from src.models import Interpretation
from src.privacy_sanction_resolver import PrivacySanctionResolver
from tests.fakes import FakeLawGateway


class PrivacySanctionResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gateway = FakeLawGateway()
        self.resolver = PrivacySanctionResolver(self.gateway)
        self.privacy_law = self.gateway.resolve_law_family("개인정보 보호법")

    def test_references_article_does_not_confuse_article_24_and_24_2(self):
        self.assertFalse(
            PrivacySanctionResolver.references_article("제24조의2제1항을 위반하여 주민등록번호를 처리한 자", "제24조")
        )
        self.assertTrue(
            PrivacySanctionResolver.references_article("제24조제1항을 위반하여 고유식별정보를 처리한 자", "제24조")
        )

    def test_resolve_returns_empty_for_non_sanction_question(self):
        article = self.gateway.get_article(self.privacy_law, "제26조")
        interpretation = Interpretation(
            intent="requirements",
            query_mode="single_basis",
        )

        sanctions = self.resolver.resolve(
            interpretation=interpretation,
            primary_law=self.privacy_law,
            article=article,
            user_query="개인정보 처리위탁은 어떤 조문이야?",
        )

        self.assertEqual(sanctions, [])

    def test_resolve_returns_empty_for_non_privacy_law(self):
        network_law = self.gateway.resolve_law_family("정보통신망 이용촉진 및 정보보호 등에 관한 법률")
        article = self.gateway.get_article(network_law, "제50조")
        interpretation = Interpretation(
            intent="illegality",
            query_mode="single_basis",
            privacy_categories=["제재/책임"],
        )

        sanctions = self.resolver.resolve(
            interpretation=interpretation,
            primary_law=network_law,
            article=article,
            user_query="문자 광고를 계속 보내면 과태료가 있나?",
        )

        self.assertEqual(sanctions, [])

    def test_resolve_returns_empty_without_explicit_legality_terms(self):
        article = self.gateway.get_article(self.privacy_law, "제17조")
        interpretation = Interpretation(
            intent="illegality",
            query_mode="single_basis",
            privacy_categories=["제재/책임"],
        )

        sanctions = self.resolver.resolve(
            interpretation=interpretation,
            primary_law=self.privacy_law,
            article=article,
            user_query="동의 없이 개인정보를 제3자에게 제공하면 어떤 조문이야?",
        )

        self.assertEqual(sanctions, [])

    def test_resolve_prefers_fine_clause_for_entrustment_contract_question(self):
        article = self.gateway.get_article(self.privacy_law, "제26조")
        interpretation = Interpretation(
            intent="requirements",
            query_mode="single_basis",
            privacy_categories=["제재/책임"],
        )

        sanctions = self.resolver.resolve(
            interpretation=interpretation,
            primary_law=self.privacy_law,
            article=article,
            user_query="개인정보 처리위탁 계약서를 문서로 하지 않으면 과태료가 있나?",
        )

        self.assertEqual(sanctions[0]["article_no"], "제75조")
        self.assertEqual(sanctions[0]["matched_clauses"][0]["match_label"], "제75조 제4항 제4호")
        self.assertIn("1천만원 이하의 과태료", sanctions[0]["penalty_summary"])

    def test_resolve_matches_criminal_penalty_for_third_party_provision(self):
        article = self.gateway.get_article(self.privacy_law, "제17조")
        interpretation = Interpretation(
            intent="illegality",
            query_mode="single_basis",
        )

        sanctions = self.resolver.resolve(
            interpretation=interpretation,
            primary_law=self.privacy_law,
            article=article,
            user_query="동의 없이 개인정보를 제3자에게 제공하면 처벌받나?",
        )

        self.assertEqual(sanctions[0]["article_no"], "제71조")
        self.assertEqual(sanctions[0]["matched_clauses"][0]["match_label"], "제71조 제1호")
        self.assertIn("5년 이하의 징역 또는 5천만원 이하의 벌금", sanctions[0]["penalty_summary"])

    def test_resolve_returns_empty_when_sanction_source_shape_is_missing(self):
        class MissingSourceLawGateway(FakeLawGateway):
            def get_article(self, law, article_no):
                payload = super().get_article(law, article_no)
                if article_no == "제71조":
                    raw = dict(payload.get("raw") or {})
                    raw["source"] = {}
                    payload = {**payload, "raw": raw, "source": {}}
                return payload

        gateway = MissingSourceLawGateway()
        resolver = PrivacySanctionResolver(gateway)
        privacy_law = gateway.resolve_law_family("개인정보 보호법")
        article = gateway.get_article(privacy_law, "제17조")
        interpretation = Interpretation(
            intent="illegality",
            query_mode="single_basis",
        )

        sanctions = resolver.resolve(
            interpretation=interpretation,
            primary_law=privacy_law,
            article=article,
            user_query="동의 없이 개인정보를 제3자에게 제공하면 처벌받나?",
        )

        self.assertEqual(sanctions, [])


if __name__ == "__main__":
    unittest.main()
