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


def _normalize_match_text(text: str) -> str:
    return " ".join(str(text or "").split()).casefold()


def _contains_term(query: str, term: str) -> bool:
    normalized_term = _normalize_match_text(term)
    return bool(normalized_term) and normalized_term in query


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
        normalized_query = _normalize_match_text(query)
        candidate_laws = list(interpretation.candidate_law_families)
        direct_basis = list(interpretation.candidate_direct_basis_articles)
        related_basis = list(interpretation.preferred_related_basis)
        framework_axes = list(interpretation.framework_axes)
        matched_policy_ids = list(interpretation.matched_policy_ids)
        matched_privacy_profiles = sorted(
            (
                profile
                for profile in self.privacy_profiles
                if self._matches_privacy_profile(profile, normalized_query, interpretation.query_mode)
            ),
            key=lambda profile: self._privacy_profile_sort_key(profile, normalized_query),
            reverse=True,
        )

        matched_profile_candidates: List[str] = []
        matched_profile_direct_basis: List[DirectBasisCandidate] = []
        matched_profile_related_basis: List[DirectBasisCandidate] = []
        for profile in matched_privacy_profiles:
            profile_id = str(profile.get("id") or "")
            if profile_id:
                matched_policy_ids.append(profile_id)
            law_families = [str(item).strip() for item in profile.get("scope", {}).get("law_families", []) if str(item).strip()]
            matched_profile_candidates.extend(law_families)
            if law_families:
                matched_profile_direct_basis.extend(
                    DirectBasisCandidate(
                        law_family=law_families[0],
                        article_no=article_no,
                        reason=f"profile:{profile_id}",
                    )
                    for article_no in profile.get("direct_basis", [])
                    if isinstance(article_no, str) and article_no.startswith("제")
                )
                matched_profile_related_basis.extend(
                    DirectBasisCandidate(
                        law_family=law_families[0],
                        article_no=article_no,
                        reason=f"profile_related:{profile_id}",
                    )
                    for article_no in profile.get("related_basis", [])
                    if isinstance(article_no, str) and article_no.startswith("제")
                )

        candidate_laws.extend(matched_profile_candidates)
        direct_basis = matched_profile_direct_basis + direct_basis
        related_basis = matched_profile_related_basis + related_basis

        if interpretation.query_mode == "framework_overview":
            query_aspects = self._framework_query_aspects(normalized_query, interpretation)
            for profile in self.framework_profiles:
                if self._matches_framework_profile(profile, normalized_query, query_aspects):
                    framework_axes.append(
                        {
                            "axis": profile.get("axis"),
                            "law_family": profile.get("law_family"),
                            "aspects": profile.get("aspects", []),
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

    def _matches_privacy_profile(self, profile: Dict[str, Any], normalized_query: str, query_mode: str) -> bool:
        scope = profile.get("scope", {})
        query_modes = scope.get("query_modes") or scope.get("query_mode") or []
        if query_modes and query_mode not in query_modes:
            return False

        match = profile.get("match", {})
        all_terms = [str(item).strip() for item in match.get("all", []) if str(item).strip()]
        any_terms = [str(item).strip() for item in match.get("any", []) if str(item).strip()]
        none_terms = [str(item).strip() for item in match.get("none", []) if str(item).strip()]
        negative_markers = [str(item).strip() for item in profile.get("negative_article_markers", []) if str(item).strip()]

        if all_terms and not all(_contains_term(normalized_query, term) for term in all_terms):
            return False
        if any_terms and not any(_contains_term(normalized_query, term) for term in any_terms):
            return False
        if any(_contains_term(normalized_query, term) for term in none_terms):
            return False
        if any(_contains_term(normalized_query, term) for term in negative_markers):
            return False
        return bool(all_terms or any_terms)

    def _matches_framework_profile(self, profile: Dict[str, Any], normalized_query: str, query_aspects: List[str]) -> bool:
        terms = [str(item).strip() for item in profile.get("match_terms", []) if str(item).strip()]
        if not any(_contains_term(normalized_query, term) for term in terms):
            return False
        allowed_aspects = [str(item).strip() for item in (profile.get("match_aspects") or profile.get("aspects") or []) if str(item).strip()]
        if allowed_aspects and query_aspects and not set(allowed_aspects).intersection(query_aspects):
            return False
        return True

    def _privacy_profile_sort_key(self, profile: Dict[str, Any], normalized_query: str) -> tuple[int, int, int, int, int]:
        match = profile.get("match", {})
        all_terms = [str(item).strip() for item in match.get("all", []) if str(item).strip()]
        any_terms = [str(item).strip() for item in match.get("any", []) if str(item).strip()]
        none_terms = [str(item).strip() for item in match.get("none", []) if str(item).strip()]
        negative_markers = [str(item).strip() for item in profile.get("negative_article_markers", []) if str(item).strip()]
        matched_terms = [term for term in all_terms + any_terms if _contains_term(normalized_query, term)]
        max_term_length = max((len(term) for term in matched_terms), default=0)
        total_length = sum(len(item) for item in matched_terms)
        return (
            max_term_length,
            total_length,
            len(all_terms),
            len(any_terms),
            len(none_terms) + len(negative_markers),
        )

    def _framework_query_aspects(self, normalized_query: str, interpretation: Interpretation) -> List[str]:
        aspects: List[str] = []
        if "광고성정보전송" in interpretation.issue_terms or any(
            _contains_term(normalized_query, term) for term in ("광고", "문자", "이메일", "메신저", "푸시", "수신거부", "수신동의")
        ):
            aspects.append("transmission")
        if any(category == "처리 근거" for category in interpretation.privacy_categories) or any(
            issue in interpretation.issue_terms for issue in ("수집이용", "제3자제공", "위탁")
        ):
            aspects.append("processing")
        if any(category == "정보주체 권리" for category in interpretation.privacy_categories) or any(
            _contains_term(normalized_query, term) for term in ("철회", "수신거부", "열람", "정정", "삭제", "처리정지")
        ):
            aspects.append("rights")
        if any(_contains_term(normalized_query, term) for term in ("표시", "과장", "기만", "랜딩페이지", "sns", "배너")):
            aspects.append("representation")
        if any(_contains_term(normalized_query, term) for term in ("쇼핑몰", "통신판매", "소비자", "유인", "구매")):
            aspects.append("commerce")
        if any(category == "제재/책임" for category in interpretation.privacy_categories) or any(
            _contains_term(normalized_query, term) for term in ("위반", "과태료", "처벌", "제재")
        ):
            aspects.append("sanction")
        return _unique_strs(aspects)

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
