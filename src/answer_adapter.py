from __future__ import annotations

import re
import time
import uuid
from typing import Any, Dict, List, Optional

from .models import PipelineRequest, PipelineResponse, RetrievalResult


def _clean(text: Any) -> str:
    return " ".join(str(text or "").split()).strip()


class AnswerAdapter:
    def compose(
        self,
        *,
        request: PipelineRequest,
        retrieval: RetrievalResult,
        started_at: float,
    ) -> PipelineResponse:
        answer = self._build_answer(retrieval)
        clarification = None
        if retrieval.interpretation.needs_clarification and retrieval.interpretation.clarification_points:
            clarification = {
                "clarification_needed": True,
                "clarification_questions": retrieval.interpretation.clarification_points,
            }

        citations = self._build_citations(retrieval)
        answer_plan = self._build_answer_plan(retrieval, clarification)
        risk_level = self._risk_level(retrieval)
        score = 90.0 if retrieval.article else 65.0 if retrieval.framework_axes else 40.0
        return PipelineResponse(
            request_id=request.request_id or str(uuid.uuid4()),
            risk_level=risk_level,
            mode="single_agent",
            answer=answer,
            citations=citations,
            score=score,
            latency_ms=(time.time() - started_at) * 1000.0,
            error=None,
            clarification=clarification,
            answer_plan=answer_plan,
        )

    def _build_answer(self, retrieval: RetrievalResult) -> str:
        if retrieval.interpretation.query_mode == "framework_overview":
            lines = ["[결론]", "질문은 관련 법 체계를 함께 보는 유형입니다."]
            if retrieval.framework_axes:
                lines.extend(["", "[핵심 축]"])
                for axis in retrieval.framework_axes:
                    law_name = _clean(((axis.get("law") or {}) if isinstance(axis.get("law"), dict) else {}).get("law_name"))
                    article_numbers = ", ".join(axis.get("article_numbers") or [])
                    lines.append(f"- {axis.get('axis')}: {law_name} {article_numbers}".rstrip())
            return "\n".join(lines)

        if retrieval.primary_law and retrieval.article:
            article_no = retrieval.article.get("article_no")
            article_title = self._extract_article_title(_clean(retrieval.article.get("article_text")))
            lines = [
                "[결론]",
                f"{retrieval.primary_law.law_name} {article_no}가 직접 관련 조문입니다.",
                "",
                "[조문]",
                _clean(retrieval.article.get("article_text")),
            ]
            if article_title:
                lines.insert(2, f"조문 제목: {article_title}")
            if retrieval.related_articles:
                lines.extend(["", "[관련 조문]"])
                for related in retrieval.related_articles:
                    excerpt = _clean(related.get("article_text_excerpt") or related.get("article_text"))
                    lines.append(f"- {related.get('article_no')}: {excerpt}")
            lines.extend(
                [
                    "",
                    "[근거]",
                    f"- 법령: {retrieval.primary_law.law_name}",
                    f"- 조문: {article_no}",
                ]
            )
            return "\n".join(lines)

        return "[결론]\n직접 관련 조문을 특정하지 못했습니다. 관련 법령군을 다시 확인해야 합니다."

    def _build_citations(self, retrieval: RetrievalResult) -> Dict[str, Any]:
        primary_law = None
        if retrieval.primary_law:
            primary_law = {
                "law_id": retrieval.primary_law.law_id,
                "law_name": retrieval.primary_law.law_name,
                "law_link": retrieval.primary_law.law_link,
            }
        return {
            "law_search": {"used_search_query": retrieval.used_search_query},
            "law_context": {
                "query_mode": retrieval.interpretation.query_mode,
                "framework_axes": retrieval.framework_axes,
                "search_queries": retrieval.search_queries,
                "related_law_queries": retrieval.related_law_queries,
                "privacy_categories": retrieval.interpretation.privacy_categories,
                "used_search_query": retrieval.used_search_query,
                "primary_law": primary_law,
                "article": retrieval.article,
                "related_articles": retrieval.related_articles,
                "version": retrieval.version,
                "routing_source": retrieval.interpretation.routing_source,
                "issue_terms": retrieval.interpretation.issue_terms,
                "matched_policy_ids": retrieval.interpretation.matched_policy_ids,
            },
            "review_summary": {
                "requires_caution": retrieval.interpretation.routing_source != "ollama" or not retrieval.article,
                "needs_more_facts": retrieval.interpretation.needs_clarification,
                "grounded_article": bool(retrieval.article),
            },
        }

    def _build_answer_plan(
        self,
        retrieval: RetrievalResult,
        clarification: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        direct_basis = None
        if retrieval.primary_law and retrieval.article:
            direct_basis = {
                "law_name": retrieval.primary_law.law_name,
                "article_no": retrieval.article.get("article_no"),
                "article_title": self._extract_article_title(_clean(retrieval.article.get("article_text"))),
                "found": True,
            }
        privacy_processing_question = bool(retrieval.interpretation.privacy_categories)
        privacy_analysis = None
        if privacy_processing_question:
            privacy_analysis = {
                "processing_actions": self._privacy_processing_actions(retrieval.interpretation.issue_terms),
                "legal_basis_checkpoints": self._privacy_legal_checkpoints(retrieval),
                "clarification_needed": bool(clarification),
            }
        return {
            "intent": retrieval.interpretation.intent,
            "risk_level": self._risk_level(retrieval),
            "query_mode": retrieval.interpretation.query_mode,
            "framework_axes": retrieval.framework_axes,
            "direct_basis": direct_basis,
            "question_law_scope": {
                "reference_queries": retrieval.search_queries,
                "target_law_family": retrieval.primary_law.law_name if retrieval.primary_law else None,
                "primary_law": {
                    "law_id": retrieval.primary_law.law_id,
                    "law_name": retrieval.primary_law.law_name,
                }
                if retrieval.primary_law
                else None,
                "article": retrieval.article,
                "direct_basis_found": bool(retrieval.article),
            },
            "supplementary_basis": None,
            "privacy_categories": retrieval.interpretation.privacy_categories,
            "privacy_processing_question": privacy_processing_question,
            "processing_actions": self._privacy_processing_actions(retrieval.interpretation.issue_terms),
            "privacy_analysis": privacy_analysis,
            "clarification": clarification,
        }

    @staticmethod
    def _extract_article_title(article_text: str) -> Optional[str]:
        match = re.search(r"제\s*\d+\s*조(?:의\s*\d+)?\(([^)]+)\)", article_text)
        if match:
            return _clean(match.group(1))
        return None

    @staticmethod
    def _risk_level(retrieval: RetrievalResult) -> str:
        if retrieval.article and retrieval.interpretation.routing_source == "ollama":
            return "LOW"
        if retrieval.article or retrieval.framework_axes:
            return "MEDIUM"
        return "HIGH"

    @staticmethod
    def _privacy_processing_actions(issue_terms: List[str]) -> List[str]:
        actions: List[str] = []
        if "수집이용" in issue_terms:
            actions.extend(["수집", "이용"])
        if "제3자제공" in issue_terms:
            actions.append("제공")
        if "위탁" in issue_terms:
            actions.append("위탁")
        if "보존파기" in issue_terms:
            actions.append("보관/파기")
        return actions

    def _privacy_legal_checkpoints(self, retrieval: RetrievalResult) -> List[str]:
        article_no = _clean((retrieval.article or {}).get("article_no"))
        law_name = retrieval.primary_law.law_name if retrieval.primary_law else "개인정보 보호법"
        checkpoints: List[str] = []
        if article_no:
            checkpoints.append(f"{law_name} {article_no}")
        for related in retrieval.related_articles:
            related_no = _clean(related.get("article_no"))
            if related_no:
                checkpoints.append(f"{law_name} {related_no}")
        return checkpoints
