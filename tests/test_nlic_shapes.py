from __future__ import annotations

import re
import unittest
from typing import Any, Dict, List

from src.models import Interpretation
from src.privacy_sanction_resolver import PrivacySanctionResolver
from tests.fakes import FakeLawGateway


def _item(number: str, text: str) -> Dict[str, str]:
    return {"호번호": number, "호내용": text}


def _paragraph(number: str, text: str, items: Any = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"항내용": text}
    if number:
        payload["항번호"] = number
    if items is not None:
        payload["호"] = items
    return payload


def _article_unit(article_no: str, title: str, heading: str, paragraphs: Any) -> Dict[str, Any]:
    match = re.search(r"제(\d+)조", article_no)
    article_number = match.group(1) if match else article_no
    payload: Dict[str, Any] = {
        "조문번호": article_number,
        "조문여부": "조문",
        "조문제목": title,
        "조문내용": heading,
    }
    if paragraphs is not None:
        payload["항"] = paragraphs
    return payload


def _source_with_units(units: List[Dict[str, Any]]) -> Dict[str, Any]:
    node: Any = units if len(units) > 1 else units[0]
    return {"법령": {"조문": {"조문단위": node}}}


class PrivacySanctionSourceShapeTests(unittest.TestCase):
    def _resolver_with_source(self, source: Dict[str, Any]) -> tuple[FakeLawGateway, PrivacySanctionResolver, object]:
        gateway = FakeLawGateway()
        privacy_law = gateway.resolve_law_family("개인정보 보호법")
        gateway.article_sources[(privacy_law.law_id, "제75조")] = source
        resolver = PrivacySanctionResolver(gateway, sanction_article_numbers=("제75조",))
        return gateway, resolver, privacy_law

    def _sanction_interpretation(self) -> Interpretation:
        return Interpretation(
            intent="requirements",
            query_mode="single_basis",
            privacy_categories=["제재/책임"],
        )

    def test_resolve_matches_when_source_contains_multiple_article_units(self):
        source = _source_with_units(
            [
                _article_unit("제74조", "과태료", "제74조(과태료)", [_paragraph("①", "제24조를 위반한 자")]),
                _article_unit(
                    "제75조",
                    "과태료",
                    "제75조(과태료)",
                    [
                        _paragraph(
                            "④",
                            "④ 다음 각 호의 어느 하나에 해당하는 자에게는 1천만원 이하의 과태료를 부과한다.",
                            [_item("4.", "제26조제1항을 위반하여 업무 위탁 시 같은 항 각 호의 내용이 포함된 문서로 하지 아니한 자")],
                        )
                    ],
                ),
            ]
        )
        gateway, resolver, privacy_law = self._resolver_with_source(source)

        sanctions = resolver.resolve(
            interpretation=self._sanction_interpretation(),
            primary_law=privacy_law,
            article=gateway.get_article(privacy_law, "제26조"),
            user_query="개인정보 처리위탁 계약서를 문서로 하지 않으면 과태료가 있나?",
        )

        self.assertEqual(sanctions[0]["article_no"], "제75조")
        self.assertEqual(sanctions[0]["matched_clauses"][0]["match_label"], "제75조 제4항 제4호")

    def test_resolve_matches_when_single_item_is_dict_not_list(self):
        source = _source_with_units(
            [
                _article_unit(
                    "제75조",
                    "과태료",
                    "제75조(과태료)",
                    _paragraph(
                        "④",
                        "④ 다음 각 호의 어느 하나에 해당하는 자에게는 1천만원 이하의 과태료를 부과한다.",
                        _item("4.", "제26조제1항을 위반하여 업무 위탁 시 같은 항 각 호의 내용이 포함된 문서로 하지 아니한 자"),
                    ),
                )
            ]
        )
        gateway, resolver, privacy_law = self._resolver_with_source(source)

        sanctions = resolver.resolve(
            interpretation=self._sanction_interpretation(),
            primary_law=privacy_law,
            article=gateway.get_article(privacy_law, "제26조"),
            user_query="개인정보 처리위탁 계약서를 문서로 하지 않으면 과태료가 있나?",
        )

        self.assertEqual(sanctions[0]["matched_clauses"][0]["match_label"], "제75조 제4항 제4호")
        self.assertIn("1천만원 이하의 과태료", sanctions[0]["penalty_summary"])

    def test_resolve_matches_when_paragraph_has_no_items(self):
        source = _source_with_units(
            [
                _article_unit(
                    "제75조",
                    "과태료",
                    "제75조(과태료)",
                    _paragraph(
                        "④",
                        "④ 제26조제1항을 위반하여 업무 위탁 시 같은 항 각 호의 내용이 포함된 문서로 하지 아니한 자에게는 1천만원 이하의 과태료를 부과한다.",
                    ),
                )
            ]
        )
        gateway, resolver, privacy_law = self._resolver_with_source(source)

        sanctions = resolver.resolve(
            interpretation=self._sanction_interpretation(),
            primary_law=privacy_law,
            article=gateway.get_article(privacy_law, "제26조"),
            user_query="개인정보 처리위탁 계약서를 문서로 하지 않으면 과태료가 있나?",
        )

        self.assertEqual(sanctions[0]["matched_clauses"][0]["match_label"], "제75조 제4항")
        self.assertIn("제26조제1항을 위반", sanctions[0]["matched_clauses"][0]["matched_text"])
        self.assertIn("1천만원 이하의 과태료", sanctions[0]["penalty_summary"])


if __name__ == "__main__":
    unittest.main()
