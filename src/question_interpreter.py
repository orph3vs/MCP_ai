from __future__ import annotations

import json
from typing import Dict, List, Optional

from .interpreter_schema import validate_interpretation_payload
from .models import DirectBasisCandidate, Interpretation, PipelineRequest
from .ollama_client import OllamaClient


LAW_ALIASES: Dict[str, str] = {
    "개보법": "개인정보 보호법",
    "개인정보보호법": "개인정보 보호법",
    "개인정보 보호법": "개인정보 보호법",
    "정보통신망법": "정보통신망 이용촉진 및 정보보호 등에 관한 법률",
    "정보통신망 이용촉진 및 정보보호 등에 관한 법률": "정보통신망 이용촉진 및 정보보호 등에 관한 법률",
    "전자상거래법": "전자상거래 등에서의 소비자보호에 관한 법률",
    "전자상거래 등에서의 소비자보호에 관한 법률": "전자상거래 등에서의 소비자보호에 관한 법률",
    "표시광고법": "표시ㆍ광고의 공정화에 관한 법률",
    "표시ㆍ광고의 공정화에 관한 법률": "표시ㆍ광고의 공정화에 관한 법률",
    "신용정보법": "신용정보의 이용 및 보호에 관한 법률",
    "신용정보의 이용 및 보호에 관한 법률": "신용정보의 이용 및 보호에 관한 법률",
}


def _clean(text: Optional[str]) -> str:
    return " ".join(str(text or "").split()).strip()


def _has_incident_loss_terms(query: str) -> bool:
    direct_terms = ("유출", "분실", "도난", "통지", "신고", "72시간", "소실")
    deletion_incident_terms = ("삭제되", "삭제 되", "삭제됨", "삭제된", "무단 삭제", "임의 삭제")
    return any(token in query for token in direct_terms) or any(token in query for token in deletion_incident_terms)


def _has_privacy_context(query: str) -> bool:
    privacy_tokens = ("개인정보", "개보법", "개인정보보호법", "주민등록번호", "민감정보", "고유식별정보", "영상정보", "정보주체")
    lowered = query.lower()
    return any(token in query for token in privacy_tokens) or "cctv" in lowered


def _is_privacy_processing_query(query: str) -> bool:
    processing_tokens = (
        "수집",
        "이용",
        "수집·이용",
        "수집 이용",
        "제3자 제공",
        "제3자제공",
        "위탁",
        "처리위탁",
        "열람",
        "정정",
        "삭제",
        "처리정지",
        "보유기간",
        "보존기간",
        "파기",
    )
    return _has_privacy_context(query) and any(token in query for token in processing_tokens)


class QuestionInterpreter:
    def __init__(self, ollama_client: Optional[OllamaClient] = None) -> None:
        self.ollama_client = ollama_client or OllamaClient()

    def interpret(self, request: PipelineRequest) -> Interpretation:
        diagnostics: List[str] = []
        try:
            prompt = self._build_prompt(request.user_query, request.context)
            payload = self.ollama_client.interpret(prompt)
            normalized = validate_interpretation_payload(payload)
            return self._from_payload(normalized, routing_source="ollama")
        except Exception as exc:  # noqa: BLE001
            diagnostics.append(str(exc))
            fallback = self._rules_fallback(request.user_query)
            return Interpretation(
                intent=fallback.intent,
                query_mode=fallback.query_mode,
                explicit_law_families=fallback.explicit_law_families,
                candidate_law_families=fallback.candidate_law_families,
                issue_terms=fallback.issue_terms,
                privacy_categories=fallback.privacy_categories,
                candidate_direct_basis_articles=fallback.candidate_direct_basis_articles,
                preferred_related_basis=fallback.preferred_related_basis,
                framework_axes=fallback.framework_axes,
                needs_clarification=fallback.needs_clarification,
                clarification_points=fallback.clarification_points,
                routing_source="rules_fallback",
                diagnostics=diagnostics,
                matched_policy_ids=fallback.matched_policy_ids,
            )

    def _from_payload(self, payload: Dict[str, object], routing_source: str) -> Interpretation:
        return Interpretation(
            intent=str(payload["intent"]),
            query_mode=str(payload["query_mode"]),
            explicit_law_families=list(payload["explicit_law_families"]),
            candidate_law_families=list(payload["candidate_law_families"]),
            issue_terms=list(payload["issue_terms"]),
            privacy_categories=list(payload["privacy_categories"]),
            candidate_direct_basis_articles=[
                DirectBasisCandidate(
                    law_family=item["law_family"],
                    article_no=item["article_no"],
                    reason=item.get("reason", ""),
                )
                for item in payload["candidate_direct_basis_articles"]
            ],
            needs_clarification=bool(payload["needs_clarification"]),
            clarification_points=list(payload["clarification_points"]),
            routing_source=routing_source,
        )

    def _build_prompt(self, user_query: str, context: Optional[str]) -> str:
        schema = {
            "intent": "difference|requirements|procedure|illegality|applicability|explain",
            "query_mode": "single_basis|framework_overview",
            "explicit_law_families": ["..."],
            "candidate_law_families": ["..."],
            "issue_terms": ["..."],
            "privacy_categories": ["처리 근거", "정보주체 권리", "절차/방법", "보존/파기", "제재/책임", "적용 범위/주체"],
            "candidate_direct_basis_articles": [{"law_family": "...", "article_no": "제15조", "reason": "..."}],
            "needs_clarification": False,
            "clarification_points": [],
        }
        parts = [
            "한국 법률 질문을 해석하는 라우팅 모델이다.",
            "반드시 JSON object 하나만 출력한다.",
            "최종 정답이나 장문 설명은 쓰지 않는다.",
            "law family는 실제 법령군 명칭을 쓴다.",
            f"JSON schema example: {json.dumps(schema, ensure_ascii=False)}",
            f"user_query: {user_query}",
        ]
        if _clean(context):
            parts.append(f"context: {_clean(context)}")
        return "\n".join(parts)

    def _rules_fallback(self, user_query: str) -> Interpretation:
        query = _clean(user_query)
        explicit_laws = self._extract_explicit_laws(query)
        candidate_laws = list(explicit_laws)
        issue_terms = self._extract_issue_terms(query)
        privacy_categories = self._extract_privacy_categories(query)
        query_mode = self._query_mode(query)
        intent = self._intent(query)

        if "개인정보" in query or privacy_categories:
            if "개인정보 보호법" not in candidate_laws:
                candidate_laws.append("개인정보 보호법")

        if "광고성정보전송" in issue_terms and "정보통신망 이용촉진 및 정보보호 등에 관한 법률" not in candidate_laws:
            candidate_laws.append("정보통신망 이용촉진 및 정보보호 등에 관한 법률")

        direct_basis = self._fallback_direct_basis(query, candidate_laws, issue_terms)
        framework_axes: List[Dict[str, object]] = []
        if query_mode == "framework_overview":
            framework_axes = [{"axis": "관련 법체계", "query": query}]

        return Interpretation(
            intent=intent,
            query_mode=query_mode,
            explicit_law_families=explicit_laws,
            candidate_law_families=candidate_laws,
            issue_terms=issue_terms,
            privacy_categories=privacy_categories,
            candidate_direct_basis_articles=direct_basis,
            framework_axes=framework_axes,
            routing_source="rules_fallback",
        )

    def _extract_explicit_laws(self, query: str) -> List[str]:
        lowered = query.lower()
        results: List[str] = []
        for alias, law_family in LAW_ALIASES.items():
            if alias.lower() in lowered and law_family not in results:
                results.append(law_family)
        return results

    def _extract_issue_terms(self, query: str) -> List[str]:
        issues: List[str] = []
        if any(token in query for token in ("광고성 정보", "광고성정보", "영리목적", "수신거부", "스팸", "야간 전송")):
            issues.append("광고성정보전송")
        if any(token in query.lower() for token in ("cctv",)) or any(token in query for token in ("영상정보", "영상정보처리기기", "고정형")):
            issues.append("영상정보")
        if _has_incident_loss_terms(query):
            issues.append("유출통지")
        if any(token in query for token in ("보유기간", "보존기간", "보관", "파기", "분리보관", "지체 없이", "지체없이")):
            issues.append("보존파기")
        if any(token in query for token in ("수집", "수집·이용", "수집 이용")):
            issues.append("수집이용")
        if any(token in query for token in ("제3자 제공", "제3자제공", "외부 제공", "공유", "넘겨")):
            issues.append("제3자제공")
        if any(token in query for token in ("위탁", "수탁", "처리위탁")):
            issues.append("위탁")
        return issues

    def _extract_privacy_categories(self, query: str) -> List[str]:
        if not _has_privacy_context(query):
            return []
        categories: List[str] = []
        if _is_privacy_processing_query(query):
            categories.append("처리 근거")
        if any(token in query for token in ("열람", "정정", "삭제", "처리정지", "철회", "탈퇴")):
            categories.append("정보주체 권리")
        if any(token in query for token in ("절차", "방법", "어떻게", "고지", "안내")):
            categories.append("절차/방법")
        if any(token in query for token in ("보유기간", "보존기간", "파기", "분리보관")):
            categories.append("보존/파기")
        if any(token in query for token in ("위반", "과태료", "벌칙", "처벌", "제재")):
            categories.append("제재/책임")
        if any(token in query for token in ("수탁자", "관리주체", "개인정보처리자", "누가", "기관", "사업자")):
            categories.append("적용 범위/주체")
        return categories

    def _query_mode(self, query: str) -> str:
        if any(token in query for token in ("관련 법", "법적 근거", "체계", "정리", "어떤 법")):
            return "framework_overview"
        return "single_basis"

    def _intent(self, query: str) -> str:
        if any(token in query for token in ("차이", "비교", "구분")):
            return "difference"
        if any(token in query for token in ("절차", "방법", "어떻게")):
            return "procedure"
        if any(token in query for token in ("위법", "불법", "과태료", "처벌", "제재")):
            return "illegality"
        if any(token in query for token in ("적용", "해당", "대상", "되는지", "될까요")):
            return "applicability"
        if any(token in query for token in ("요건", "조건", "가능", "수 있", "해도 되")):
            return "requirements"
        return "explain"

    def _fallback_direct_basis(
        self,
        query: str,
        candidate_laws: List[str],
        issue_terms: List[str],
    ) -> List[DirectBasisCandidate]:
        results: List[DirectBasisCandidate] = []
        privacy_law = "개인정보 보호법"
        network_law = "정보통신망 이용촉진 및 정보보호 등에 관한 법률"
        if "주민등록번호" in query:
            results.append(DirectBasisCandidate(privacy_law, "제24조의2", "rules fallback"))
        elif "민감정보" in query:
            results.append(DirectBasisCandidate(privacy_law, "제23조", "rules fallback"))
        elif "고유식별정보" in query:
            results.append(DirectBasisCandidate(privacy_law, "제24조", "rules fallback"))
        elif any(token in query for token in ("제3자 제공", "외부 제공", "공유", "넘겨")):
            results.append(DirectBasisCandidate(privacy_law, "제17조", "rules fallback"))
        elif any(token in query for token in ("위탁", "수탁", "처리위탁", "외부 업체에 맡")):
            results.append(DirectBasisCandidate(privacy_law, "제26조", "rules fallback"))
        elif any(token in query for token in ("보유기간", "보존기간", "파기", "분리보관")):
            results.append(DirectBasisCandidate(privacy_law, "제21조", "rules fallback"))
        elif any(token in query for token in ("열람", "열람청구")):
            results.append(DirectBasisCandidate(privacy_law, "제35조", "rules fallback"))
        elif any(token in query for token in ("정정", "삭제", "수정")):
            results.append(DirectBasisCandidate(privacy_law, "제36조", "rules fallback"))
        elif "처리정지" in query:
            results.append(DirectBasisCandidate(privacy_law, "제37조", "rules fallback"))
        elif any(token in query.lower() for token in ("cctv",)) or "영상정보" in query:
            results.append(DirectBasisCandidate(privacy_law, "제25조", "rules fallback"))
        elif "광고성정보전송" in issue_terms:
            results.append(DirectBasisCandidate(network_law, "제50조", "rules fallback"))
        elif _is_privacy_processing_query(query) and privacy_law in candidate_laws:
            results.append(DirectBasisCandidate(privacy_law, "제15조", "rules fallback"))
        return results
