from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class PipelineRequest:
    user_query: str
    context: Optional[str] = None
    request_id: Optional[str] = None


@dataclass(frozen=True)
class PipelineResponse:
    request_id: str
    risk_level: str
    mode: str
    answer: str
    citations: Dict[str, Any]
    score: float
    latency_ms: float
    error: Optional[Dict[str, str]] = None
    clarification: Optional[Dict[str, Any]] = None
    answer_plan: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class DirectBasisCandidate:
    law_family: str
    article_no: str
    reason: str = ""


@dataclass(frozen=True)
class Interpretation:
    intent: str
    query_mode: str
    explicit_law_families: List[str] = field(default_factory=list)
    candidate_law_families: List[str] = field(default_factory=list)
    issue_terms: List[str] = field(default_factory=list)
    privacy_categories: List[str] = field(default_factory=list)
    candidate_direct_basis_articles: List[DirectBasisCandidate] = field(default_factory=list)
    preferred_related_basis: List[DirectBasisCandidate] = field(default_factory=list)
    framework_axes: List[Dict[str, Any]] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_points: List[str] = field(default_factory=list)
    routing_source: str = "rules_fallback"
    diagnostics: List[str] = field(default_factory=list)
    matched_policy_ids: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResolvedLaw:
    law_id: str
    law_name: str
    law_link: Optional[str] = None
    law_type: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class RetrievalResult:
    interpretation: Interpretation
    primary_law: Optional[ResolvedLaw]
    article: Optional[Dict[str, Any]]
    related_articles: List[Dict[str, Any]]
    framework_axes: List[Dict[str, Any]]
    used_search_query: Optional[str]
    search_queries: List[str]
    related_law_queries: List[str]
    version: Optional[Dict[str, Any]]
    precedent: Optional[Dict[str, Any]]
    sanction_articles: List[Dict[str, Any]]
