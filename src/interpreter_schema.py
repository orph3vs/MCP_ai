from __future__ import annotations

from typing import Any, Dict, List


INTENTS = (
    "difference",
    "requirements",
    "procedure",
    "illegality",
    "applicability",
    "explain",
)

QUERY_MODES = ("single_basis", "framework_overview")

PRIVACY_CATEGORIES = (
    "처리 근거",
    "정보주체 권리",
    "절차/방법",
    "보존/파기",
    "제재/책임",
    "적용 범위/주체",
)


def _normalize_str_list(value: Any, field_name: str) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    normalized: List[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} items must be strings")
        text = item.strip()
        if text:
            normalized.append(text)
    return normalized


def validate_interpretation_payload(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("interpretation payload must be an object")

    intent = str(payload.get("intent") or "explain").strip()
    if intent not in INTENTS:
        raise ValueError(f"invalid intent: {intent}")

    query_mode = str(payload.get("query_mode") or "single_basis").strip()
    if query_mode not in QUERY_MODES:
        raise ValueError(f"invalid query_mode: {query_mode}")

    privacy_categories = _normalize_str_list(payload.get("privacy_categories"), "privacy_categories")
    invalid_categories = [item for item in privacy_categories if item not in PRIVACY_CATEGORIES]
    if invalid_categories:
        raise ValueError(f"invalid privacy_categories: {invalid_categories}")

    direct_basis_raw = payload.get("candidate_direct_basis_articles")
    if direct_basis_raw is None:
        direct_basis_raw = []
    if not isinstance(direct_basis_raw, list):
        raise ValueError("candidate_direct_basis_articles must be a list")

    candidate_direct_basis_articles: List[Dict[str, str]] = []
    for item in direct_basis_raw:
        if not isinstance(item, dict):
            raise ValueError("candidate_direct_basis_articles items must be objects")
        law_family = str(item.get("law_family") or "").strip()
        article_no = str(item.get("article_no") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if not law_family or not article_no:
            raise ValueError("candidate_direct_basis_articles items require law_family and article_no")
        candidate_direct_basis_articles.append(
            {
                "law_family": law_family,
                "article_no": article_no,
                "reason": reason,
            }
        )

    return {
        "intent": intent,
        "query_mode": query_mode,
        "explicit_law_families": _normalize_str_list(payload.get("explicit_law_families"), "explicit_law_families"),
        "candidate_law_families": _normalize_str_list(payload.get("candidate_law_families"), "candidate_law_families"),
        "issue_terms": _normalize_str_list(payload.get("issue_terms"), "issue_terms"),
        "privacy_categories": privacy_categories,
        "candidate_direct_basis_articles": candidate_direct_basis_articles,
        "needs_clarification": bool(payload.get("needs_clarification", False)),
        "clarification_points": _normalize_str_list(payload.get("clarification_points"), "clarification_points"),
    }
