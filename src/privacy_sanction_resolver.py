from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

from .law_gateway import LawGateway
from .models import Interpretation, ResolvedLaw


PRIVACY_LAW_NAME = "개인정보 보호법"
DEFAULT_PRIVACY_SANCTION_ARTICLES = ("제70조", "제71조", "제72조", "제73조", "제75조")
LEGALITY_REVIEW_TERMS = (
    "적법",
    "합법",
    "위법",
    "불법",
    "위반",
    "과태료",
    "벌금",
    "징역",
    "처벌",
    "벌칙",
    "제재",
    "형사",
    "형사처벌",
    "고발",
)
_CIRCLED_PARAGRAPH_NUMBERS = {
    "①": "제1항",
    "②": "제2항",
    "③": "제3항",
    "④": "제4항",
    "⑤": "제5항",
    "⑥": "제6항",
    "⑦": "제7항",
    "⑧": "제8항",
    "⑨": "제9항",
    "⑩": "제10항",
}


def _clean(text: object) -> str:
    return " ".join(str(text or "").split()).strip()


def _as_list(node: object) -> List[object]:
    if isinstance(node, list):
        return node
    if isinstance(node, dict):
        return [node]
    return []


class PrivacySanctionResolver:
    def __init__(
        self,
        law_gateway: LawGateway,
        sanction_article_numbers: Sequence[str] = DEFAULT_PRIVACY_SANCTION_ARTICLES,
    ) -> None:
        self.law_gateway = law_gateway
        self.sanction_article_numbers = tuple(sanction_article_numbers)

    def resolve(
        self,
        *,
        interpretation: Interpretation,
        primary_law: Optional[ResolvedLaw],
        article: Optional[Dict[str, object]],
        user_query: str,
    ) -> List[Dict[str, object]]:
        if (
            primary_law is None
            or article is None
            or primary_law.law_name != PRIVACY_LAW_NAME
            or not self.needs_review(interpretation, user_query)
        ):
            return []

        target_article_no = _clean(article.get("article_no"))
        if not target_article_no:
            return []

        sanctions: List[Dict[str, object]] = []
        for sanction_article_no in self.sanction_article_numbers:
            resolved = self.law_gateway.get_article(primary_law, sanction_article_no)
            if not resolved.get("found"):
                continue
            matched_clauses = self._extract_sanction_matches(resolved, target_article_no, user_query)
            if not matched_clauses:
                continue
            sanctions.append(
                {
                    **resolved,
                    "sanction_type": self._extract_article_title(_clean(resolved.get("article_text"))),
                    "matched_clauses": matched_clauses,
                    "penalty_summary": matched_clauses[0].get("penalty_summary"),
                }
            )
        sanctions.sort(
            key=lambda item: (
                self._sanction_priority(user_query, _clean(item.get("sanction_type"))),
                _clean(item.get("article_no")),
            )
        )
        return sanctions

    @staticmethod
    def needs_review(interpretation: Interpretation, user_query: str) -> bool:
        has_interpretation_signal = interpretation.intent == "illegality" or any(
            category == "제재/책임" for category in interpretation.privacy_categories
        )
        if not has_interpretation_signal:
            return False
        normalized_query = _clean(user_query)
        return any(term in normalized_query for term in LEGALITY_REVIEW_TERMS)

    @staticmethod
    def references_article(text: str, target_article_no: str) -> bool:
        compact_text = re.sub(r"\s+", "", text)
        compact_target = re.sub(r"\s+", "", target_article_no)
        if not compact_target:
            return False
        pattern = re.compile(re.escape(compact_target) + r"(?!의\d)")
        return bool(pattern.search(compact_text))

    def _extract_sanction_matches(
        self,
        sanction_article: Dict[str, object],
        target_article_no: str,
        user_query: str,
    ) -> List[Dict[str, object]]:
        raw = sanction_article.get("raw")
        source = raw.get("source") if isinstance(raw, dict) else None
        unit = self._select_article_unit(source, _clean(sanction_article.get("article_no")))
        if unit is None:
            return []

        article_no = _clean(sanction_article.get("article_no"))
        article_heading = _clean(unit.get("조문내용") or sanction_article.get("article_text"))
        matches: List[Dict[str, object]] = []
        paragraphs = _as_list(unit.get("항"))
        if not paragraphs:
            return matches

        for paragraph in paragraphs:
            if not isinstance(paragraph, dict):
                continue
            paragraph_label = self._paragraph_label(_clean(paragraph.get("항번호")))
            paragraph_summary = _clean(paragraph.get("항내용")) or article_heading
            items = _as_list(paragraph.get("호"))
            if not items:
                if self.references_article(paragraph_summary, target_article_no):
                    matches.append(
                        {
                            "match_label": self._join_match_label(article_no, paragraph_label),
                            "matched_text": paragraph_summary,
                            "penalty_summary": paragraph_summary,
                            "match_score": self._clause_query_score(paragraph_summary, user_query),
                        }
                    )
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_text = _clean(item.get("호내용"))
                if not self.references_article(item_text, target_article_no):
                    continue
                matches.append(
                    {
                        "match_label": self._join_match_label(
                            article_no,
                            paragraph_label,
                            self._item_label(_clean(item.get("호번호"))),
                        ),
                        "matched_text": item_text,
                        "penalty_summary": paragraph_summary,
                        "match_score": self._clause_query_score(item_text, user_query),
                    }
                )
        matches.sort(key=lambda item: item.get("match_score", 0), reverse=True)
        for match in matches:
            match.pop("match_score", None)
        return matches[:3]

    @staticmethod
    def _select_article_unit(source: object, article_no: str) -> Optional[Dict[str, object]]:
        if not isinstance(source, dict):
            return None
        law = source.get("법령")
        jo = law.get("조문") if isinstance(law, dict) else None
        units = _as_list(jo.get("조문단위") if isinstance(jo, dict) else None)
        target_number = re.sub(r"\D", "", article_no)
        for unit in units:
            if not isinstance(unit, dict):
                continue
            if unit.get("조문여부") != "조문":
                continue
            unit_number = re.sub(r"\D", "", str(unit.get("조문번호") or ""))
            if unit_number == target_number:
                return unit
        return None

    @staticmethod
    def _extract_article_title(article_text: str) -> Optional[str]:
        match = re.search(r"제\s*\d+\s*조(?:의\s*\d+)?\(([^)]+)\)", article_text)
        if match:
            return _clean(match.group(1))
        return None

    @staticmethod
    def _paragraph_label(paragraph_no: str) -> str:
        compact = paragraph_no.strip()
        return _CIRCLED_PARAGRAPH_NUMBERS.get(compact, compact)

    @staticmethod
    def _item_label(item_no: str) -> str:
        compact = item_no.strip().rstrip(".")
        if not compact:
            return ""
        return f"제{compact}호"

    @staticmethod
    def _join_match_label(article_no: str, paragraph_label: str, item_label: str = "") -> str:
        parts = [article_no]
        if paragraph_label:
            parts.append(paragraph_label)
        if item_label:
            parts.append(item_label)
        return " ".join(parts)

    @staticmethod
    def _sanction_priority(user_query: str, sanction_type: str) -> int:
        normalized_query = _clean(user_query)
        if "과태료" in normalized_query:
            return 0 if sanction_type == "과태료" else 1
        if any(token in normalized_query for token in ("벌금", "징역", "처벌", "벌칙")):
            return 0 if sanction_type == "벌칙" else 1
        return 0

    @staticmethod
    def _clause_query_score(text: str, user_query: str) -> int:
        normalized_text = _clean(text)
        raw_tokens = [token for token in re.findall(r"[0-9A-Za-z가-힣]+", _clean(user_query)) if len(token) >= 2]
        normalized_tokens = set()
        for token in raw_tokens:
            normalized_tokens.add(token)
            if len(token) > 2 and token[-1] in "은는이가을를로의와과도만":
                normalized_tokens.add(token[:-1])
        return sum(1 for token in normalized_tokens if token and token in normalized_text)
