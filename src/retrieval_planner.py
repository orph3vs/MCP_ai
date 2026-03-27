from __future__ import annotations

import re
from typing import Dict, List, Optional

from .law_gateway import LawGateway
from .models import Interpretation, ResolvedLaw, RetrievalResult


PRIVACY_LAW_NAME = "개인정보 보호법"
PRIVACY_SANCTION_ARTICLES = ("제70조", "제71조", "제72조", "제73조", "제75조")
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


def _unique_by_article(items: List[Dict[str, object]]) -> List[Dict[str, object]]:
    seen = set()
    ordered: List[Dict[str, object]] = []
    for item in items:
        article_no = str(item.get("article_no") or "").strip()
        if not article_no or article_no in seen:
            continue
        seen.add(article_no)
        ordered.append(item)
    return ordered


def _clean(text: object) -> str:
    return " ".join(str(text or "").split()).strip()


def _as_list(node: object) -> List[object]:
    if isinstance(node, list):
        return node
    if isinstance(node, dict):
        return [node]
    return []


class RetrievalPlanner:
    def __init__(self, law_gateway: LawGateway) -> None:
        self.law_gateway = law_gateway

    def plan(self, interpretation: Interpretation, user_query: str) -> RetrievalResult:
        resolved_cache: Dict[str, ResolvedLaw] = {}
        for law_family in interpretation.explicit_law_families + interpretation.candidate_law_families:
            if law_family and law_family not in resolved_cache:
                resolved = self.law_gateway.resolve_law_family(law_family)
                if resolved:
                    resolved_cache[law_family] = resolved

        primary_law = self._select_primary_law(interpretation, resolved_cache)
        article = None
        used_search_query = primary_law.law_name if primary_law else None
        related_articles: List[Dict[str, object]] = []
        version = self._safe_get_version(primary_law)

        if interpretation.query_mode != "framework_overview":
            article = self._resolve_primary_article(interpretation, primary_law, resolved_cache)
            related_articles = self._resolve_related_articles(
                interpretation=interpretation,
                primary_law=primary_law,
                article=article,
            )
        sanction_articles = self._resolve_sanction_articles(
            interpretation=interpretation,
            primary_law=primary_law,
            article=article,
            user_query=user_query,
        )

        framework_axes = self._resolve_framework_axes(interpretation, resolved_cache)
        return RetrievalResult(
            interpretation=interpretation,
            primary_law=primary_law,
            article=article,
            related_articles=related_articles,
            framework_axes=framework_axes,
            used_search_query=used_search_query,
            search_queries=list(interpretation.explicit_law_families + interpretation.candidate_law_families),
            related_law_queries=list(interpretation.candidate_law_families),
            version=version,
            precedent=None,
            sanction_articles=sanction_articles,
        )

    def _safe_get_version(self, primary_law: Optional[ResolvedLaw]) -> Optional[Dict[str, object]]:
        if primary_law is None:
            return None
        try:
            return self.law_gateway.get_version(primary_law)
        except Exception:  # noqa: BLE001
            return None

    def _select_primary_law(
        self,
        interpretation: Interpretation,
        resolved_cache: Dict[str, ResolvedLaw],
    ) -> Optional[ResolvedLaw]:
        for law_family in interpretation.explicit_law_families:
            if law_family in resolved_cache:
                return resolved_cache[law_family]
        for candidate in interpretation.candidate_direct_basis_articles:
            if candidate.law_family in resolved_cache:
                return resolved_cache[candidate.law_family]
        for law_family in interpretation.candidate_law_families:
            if law_family in resolved_cache:
                return resolved_cache[law_family]
        return None

    def _resolve_primary_article(
        self,
        interpretation: Interpretation,
        primary_law: Optional[ResolvedLaw],
        resolved_cache: Dict[str, ResolvedLaw],
    ) -> Optional[Dict[str, object]]:
        for candidate in interpretation.candidate_direct_basis_articles:
            law = resolved_cache.get(candidate.law_family)
            if law is None and not candidate.law_family:
                law = primary_law
            if law is None:
                continue
            article = self.law_gateway.get_article(law, candidate.article_no)
            if article.get("found"):
                return article

        if primary_law and interpretation.issue_terms:
            keyword_article = self.law_gateway.find_article_by_keywords(primary_law, interpretation.issue_terms)
            if keyword_article:
                return keyword_article
        return None

    def _resolve_related_articles(
        self,
        *,
        interpretation: Interpretation,
        primary_law: Optional[ResolvedLaw],
        article: Optional[Dict[str, object]],
    ) -> List[Dict[str, object]]:
        if primary_law is None:
            return []

        related: List[Dict[str, object]] = []
        for candidate in interpretation.preferred_related_basis:
            if candidate.law_family != primary_law.law_name:
                continue
            resolved = self.law_gateway.get_article(primary_law, candidate.article_no)
            if resolved.get("found"):
                related.append(resolved)

        if article and isinstance(article.get("article_text"), str):
            for article_no in self._extract_referenced_articles(article["article_text"]):
                if article_no == article.get("article_no"):
                    continue
                resolved = self.law_gateway.get_article(primary_law, article_no)
                if resolved.get("found"):
                    related.append(resolved)

        return _unique_by_article(related)

    def _resolve_framework_axes(
        self,
        interpretation: Interpretation,
        resolved_cache: Dict[str, ResolvedLaw],
    ) -> List[Dict[str, object]]:
        axes: List[Dict[str, object]] = []
        for axis in interpretation.framework_axes:
            law_family = str(axis.get("law_family") or "").strip()
            resolved = resolved_cache.get(law_family) if law_family else None
            axis_payload = dict(axis)
            if resolved:
                axis_payload["law"] = {
                    "law_id": resolved.law_id,
                    "law_name": resolved.law_name,
                    "law_link": resolved.law_link,
                }
                article_numbers = axis_payload.get("article_numbers") or []
                fetched_articles = []
                for article_no in article_numbers[:3]:
                    article = self.law_gateway.get_article(resolved, article_no)
                    if article.get("found"):
                        fetched_articles.append(article)
                axis_payload["articles"] = fetched_articles
            axes.append(axis_payload)
        return axes

    def _resolve_sanction_articles(
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
            or not self._needs_sanction_review(interpretation)
        ):
            return []

        target_article_no = _clean(article.get("article_no"))
        if not target_article_no:
            return []

        sanctions: List[Dict[str, object]] = []
        for sanction_article_no in PRIVACY_SANCTION_ARTICLES:
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
    def _needs_sanction_review(interpretation: Interpretation) -> bool:
        return interpretation.intent == "illegality" or any(
            category == "제재/책임" for category in interpretation.privacy_categories
        )

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
                if self._references_article(paragraph_summary, target_article_no):
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
                if not self._references_article(item_text, target_article_no):
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
    def _references_article(text: str, target_article_no: str) -> bool:
        compact_text = re.sub(r"\s+", "", text)
        compact_target = re.sub(r"\s+", "", target_article_no)
        if not compact_target:
            return False
        pattern = re.compile(re.escape(compact_target) + r"(?!의\d)")
        return bool(pattern.search(compact_text))

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
        tokens = [token for token in re.split(r"\s+", _clean(user_query)) if len(token) >= 2]
        return sum(1 for token in tokens if token in normalized_text)

    @staticmethod
    def _extract_referenced_articles(article_text: str) -> List[str]:
        matches = re.findall(r"제\s*\d+\s*조(?:의\s*\d+)?", article_text)
        normalized: List[str] = []
        seen = set()
        for item in matches:
            compact = re.sub(r"\s+", "", item)
            if compact not in seen:
                seen.add(compact)
                normalized.append(compact)
        return normalized
