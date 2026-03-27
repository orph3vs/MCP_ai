from __future__ import annotations

import re
from typing import Dict, List, Optional

from .law_gateway import LawGateway
from .models import Interpretation, ResolvedLaw, RetrievalResult


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
