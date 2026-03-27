from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List

from .models import DirectBasisCandidate, Interpretation


def _load_json_with_fallback(path: Path) -> Any:
    for encoding in ("utf-8", "utf-8-sig", "cp949", "euc-kr"):
        try:
            return json.loads(path.read_text(encoding=encoding))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"unable to decode json file: {path}")


def _unique_strs(items: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _unique_candidates(items: List[DirectBasisCandidate]) -> List[DirectBasisCandidate]:
    seen = set()
    ordered: List[DirectBasisCandidate] = []
    for item in items:
        key = (item.law_family, item.article_no)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered


def _has_cctv_incident_terms(query: str) -> bool:
    direct_terms = ("통지", "신고", "유출", "분실", "소실", "도난")
    deletion_incident_terms = ("삭제되", "삭제 되", "삭제됨", "삭제된", "무단 삭제", "임의 삭제")
    return any(token in query for token in direct_terms) or any(token in query for token in deletion_incident_terms)


class PolicyEngine:
    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir
        self.privacy_profiles = _load_json_with_fallback(config_dir / "privacy_direct_basis_profiles.json")
        self.framework_profiles = _load_json_with_fallback(config_dir / "framework_law_profiles.json")

    def apply(self, interpretation: Interpretation, user_query: str) -> Interpretation:
        query = " ".join(user_query.split())
        candidate_laws = list(interpretation.candidate_law_families)
        direct_basis = list(interpretation.candidate_direct_basis_articles)
        related_basis = list(interpretation.preferred_related_basis)
        framework_axes = list(interpretation.framework_axes)
        matched_policy_ids = list(interpretation.matched_policy_ids)

        for profile in self.privacy_profiles:
            if self._matches_privacy_profile(profile, query, interpretation.query_mode):
                profile_id = str(profile.get("id") or "")
                if profile_id:
                    matched_policy_ids.append(profile_id)
                candidate_laws.extend(profile.get("scope", {}).get("law_families", []))
                direct_basis = [
                    DirectBasisCandidate(
                        law_family=profile["scope"]["law_families"][0],
                        article_no=article_no,
                        reason=f"profile:{profile_id}",
                    )
                    for article_no in profile.get("direct_basis", [])
                    if isinstance(article_no, str) and article_no.startswith("제")
                ] + direct_basis
                related_basis.extend(
                    DirectBasisCandidate(
                        law_family=profile["scope"]["law_families"][0],
                        article_no=article_no,
                        reason=f"profile_related:{profile_id}",
                    )
                    for article_no in profile.get("related_basis", [])
                    if isinstance(article_no, str) and article_no.startswith("제")
                )

        if interpretation.query_mode == "framework_overview":
            for profile in self.framework_profiles:
                if self._matches_framework_profile(profile, query):
                    framework_axes.append(
                        {
                            "axis": profile.get("axis"),
                            "law_family": profile.get("law_family"),
                            "article_numbers": profile.get("article_numbers", []),
                            "description": profile.get("description"),
                        }
                    )
                    law_family = str(profile.get("law_family") or "").strip()
                    if law_family:
                        candidate_laws.append(law_family)

        if self._is_cctv_exception_query(query):
            privacy_law = "개인정보 보호법"
            candidate_laws.append(privacy_law)
            direct_basis = [DirectBasisCandidate(privacy_law, "제58조", "cctv_exception")] + direct_basis
            related_basis = [
                DirectBasisCandidate(privacy_law, "제25조", "cctv_exception_related"),
                DirectBasisCandidate(privacy_law, "제34조", "cctv_exception_related"),
            ] + related_basis

        if self._is_ad_transmission_query(query):
            network_law = "정보통신망 이용촉진 및 정보보호 등에 관한 법률"
            candidate_laws.append(network_law)
            direct_basis = [DirectBasisCandidate(network_law, "제50조", "ad_transmission")] + direct_basis
            related_basis = [
                DirectBasisCandidate(network_law, "제50조의8", "ad_transmission_related"),
            ] + related_basis

        return replace(
            interpretation,
            candidate_law_families=_unique_strs(candidate_laws),
            candidate_direct_basis_articles=_unique_candidates(direct_basis),
            preferred_related_basis=_unique_candidates(related_basis),
            framework_axes=framework_axes,
            matched_policy_ids=_unique_strs(matched_policy_ids),
        )

    def _matches_privacy_profile(self, profile: Dict[str, Any], query: str, query_mode: str) -> bool:
        scope = profile.get("scope", {})
        query_modes = scope.get("query_modes") or scope.get("query_mode") or []
        if query_modes and query_mode not in query_modes:
            return False

        match = profile.get("match", {})
        all_terms = [str(item).strip() for item in match.get("all", []) if str(item).strip()]
        any_terms = [str(item).strip() for item in match.get("any", []) if str(item).strip()]
        none_terms = [str(item).strip() for item in match.get("none", []) if str(item).strip()]

        if all_terms and not all(term in query for term in all_terms):
            return False
        if any_terms and not any(term in query for term in any_terms):
            return False
        if any(term in query for term in none_terms):
            return False
        return bool(all_terms or any_terms)

    def _matches_framework_profile(self, profile: Dict[str, Any], query: str) -> bool:
        terms = [str(item).strip() for item in profile.get("match_terms", []) if str(item).strip()]
        return any(term in query for term in terms)

    @staticmethod
    def _is_cctv_exception_query(query: str) -> bool:
        video = any(token in query.lower() for token in ("cctv",)) or any(
            token in query for token in ("영상정보", "영상정보처리기기", "고정형", "공개된 장소")
        )
        incident = _has_cctv_incident_terms(query)
        return video and incident

    @staticmethod
    def _is_ad_transmission_query(query: str) -> bool:
        return any(
            token in query
            for token in ("광고성 정보", "광고성정보", "영리목적", "수신거부", "야간 전송", "문자 광고", "스팸")
        )
