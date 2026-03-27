from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from .models import ResolvedLaw
from .nlic_api_wrapper import NlicApiWrapper


def _clean(text: Any) -> str:
    return " ".join(str(text or "").split()).strip()


class LawGateway:
    def __init__(self, api: Optional[NlicApiWrapper] = None) -> None:
        self.api = api or NlicApiWrapper()

    def search_law_raw(self, query: str) -> Dict[str, Any]:
        return self.api.search_law(query)

    def get_article_raw(self, law_id: str, article_no: str) -> Dict[str, Any]:
        return self.api.get_article(law_id, article_no)

    def get_version_raw(self, law_id: str) -> Dict[str, Any]:
        return self.api.get_version(law_id)

    def validate_article_raw(self, law_id: str, article_no: str) -> Dict[str, Any]:
        return self.api.validate_article(law_id, article_no)

    def search_precedent_raw(self, query: str) -> Dict[str, Any]:
        return self.api.search_precedent(query)

    def get_precedent_raw(self, precedent_id: str) -> Dict[str, Any]:
        return self.api.get_precedent(precedent_id)

    def resolve_law_family(self, law_family: str) -> Optional[ResolvedLaw]:
        raw = self.search_law_raw(law_family)
        items = self._normalize_law_search_results(raw)
        if not items:
            return None
        normalized_target = self._normalize_law_name(law_family)
        ranked = sorted(
            (
                {
                    **item,
                    "match_score": self._law_match_score(normalized_target, item["law_name"]),
                }
                for item in items
            ),
            key=lambda item: item["match_score"],
            reverse=True,
        )
        best = ranked[0]
        if best["match_score"] <= 0:
            return None
        return ResolvedLaw(
            law_id=best["law_id"],
            law_name=best["law_name"],
            law_link=best.get("law_link"),
            law_type=best.get("law_type"),
            raw=best.get("raw"),
        )

    def get_article(self, law: ResolvedLaw, article_no: str) -> Dict[str, Any]:
        raw = self.get_article_raw(law.law_id, article_no)
        article_text = _clean(raw.get("article_text") or raw.get("article_text_excerpt"))
        return {
            "law_id": law.law_id,
            "law_name": law.law_name,
            "article_no": _clean(raw.get("article_no") or article_no),
            "found": bool(raw.get("found")),
            "article_text": article_text,
            "article_text_excerpt": article_text[:240],
            "matched_via": raw.get("matched_via"),
            "source": raw.get("source"),
            "article_link": self._article_link(law.law_link, raw.get("article_no") or article_no),
            "raw": raw,
        }

    def find_article_by_keywords(self, law: ResolvedLaw, keywords: List[str]) -> Optional[Dict[str, Any]]:
        raw = self.api.find_article_by_keywords(law.law_id, keywords)
        if not raw:
            return None
        article_text = _clean(raw.get("article_text"))
        matched_clauses = []
        for item in raw.get("matched_clauses", []) or []:
            matched_clauses.append(
                {
                    "article_no": _clean(item.get("article_no")),
                    "article_text": _clean(item.get("article_text") or item.get("article_text_excerpt")),
                }
            )
        return {
            "law_id": law.law_id,
            "law_name": law.law_name,
            "article_no": _clean(raw.get("article_no")),
            "article_base_no": _clean(raw.get("article_base_no")),
            "found": True,
            "matched_via": raw.get("matched_via"),
            "article_text": article_text,
            "article_text_excerpt": article_text[:240],
            "article_link": self._article_link(law.law_link, raw.get("article_no")),
            "matched_clauses": matched_clauses,
            "raw": raw,
        }

    def get_version(self, law: ResolvedLaw) -> Dict[str, Any]:
        raw = self.get_version_raw(law.law_id)
        version_fields = raw.get("version_fields") if isinstance(raw, dict) else {}
        return {
            "source_target": raw.get("source_target") if isinstance(raw, dict) else None,
            "effective_date": _clean((version_fields or {}).get("시행일자")),
            "promulgation_date": _clean((version_fields or {}).get("공포일자")),
            "revision_type": _clean((version_fields or {}).get("제개정구분명") or (version_fields or {}).get("제개정구분")),
            "raw": raw,
        }

    def _normalize_law_search_results(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        container = raw.get("LawSearch") if isinstance(raw, dict) else None
        node = None
        if isinstance(container, dict):
            node = container.get("law") or container.get("laws")
        if node is None and isinstance(raw, dict):
            node = raw.get("law") or raw.get("laws")
        items = self._as_list(node)
        normalized: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            law_name = _clean(item.get("법령명한글") or item.get("law_name") or item.get("법령명"))
            law_id = _clean(item.get("법령ID") or item.get("law_id") or item.get("id"))
            if not law_name or not law_id:
                continue
            law_link = self._law_link(law_name, _clean(item.get("법령상세링크")))
            normalized.append(
                {
                    "law_id": law_id,
                    "law_name": law_name,
                    "law_type": _clean(item.get("법령구분명") or item.get("law_type")),
                    "law_link": law_link,
                    "raw": item,
                }
            )
        return normalized

    @staticmethod
    def _as_list(node: Any) -> List[Any]:
        if isinstance(node, list):
            return node
        if isinstance(node, dict):
            return [node]
        return []

    @staticmethod
    def _normalize_law_name(name: str) -> str:
        return re.sub(r"\s+", "", name)

    def _law_match_score(self, target: str, law_name: str) -> int:
        normalized = self._normalize_law_name(law_name)
        if normalized == target:
            return 100
        if normalized.startswith(target):
            if "시행령" not in law_name and "시행규칙" not in law_name:
                return 90
            return 80
        if target in normalized:
            return 60
        return 0

    @staticmethod
    def _law_link(law_name: str, raw_link: str) -> str:
        if raw_link.startswith("http://") or raw_link.startswith("https://"):
            return raw_link
        if raw_link.startswith("/"):
            return f"https://www.law.go.kr{raw_link.split('?', 1)[0]}"
        return f"https://www.law.go.kr/법령/{quote(law_name)}"

    @staticmethod
    def _article_link(law_link: Optional[str], article_no: str) -> Optional[str]:
        if not law_link or not article_no:
            return None
        normalized_article = re.sub(r"\s+", "", article_no)
        return f"{law_link.rstrip('/')}/{quote(normalized_article)}"
