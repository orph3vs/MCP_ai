from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Optional

from .answer_adapter import AnswerAdapter
from .law_gateway import LawGateway
from .models import PipelineRequest, PipelineResponse
from .policy_engine import PolicyEngine
from .question_interpreter import QuestionInterpreter
from .retrieval_planner import RetrievalPlanner


class EnginePipeline:
    def __init__(
        self,
        *,
        interpreter: Optional[QuestionInterpreter] = None,
        policy_engine: Optional[PolicyEngine] = None,
        law_gateway: Optional[LawGateway] = None,
        planner: Optional[RetrievalPlanner] = None,
        answer_adapter: Optional[AnswerAdapter] = None,
        config_dir: Optional[Path] = None,
    ) -> None:
        base_dir = Path(__file__).resolve().parent.parent
        self.law_gateway = law_gateway or LawGateway()
        self.interpreter = interpreter or QuestionInterpreter()
        self.policy_engine = policy_engine or PolicyEngine(config_dir or (base_dir / "config"))
        self.planner = planner or RetrievalPlanner(self.law_gateway)
        self.answer_adapter = answer_adapter or AnswerAdapter()

    def process(self, request: PipelineRequest) -> PipelineResponse:
        started_at = time.time()
        request_id = request.request_id or str(uuid.uuid4())
        try:
            interpretation = self.interpreter.interpret(request)
            enriched = self.policy_engine.apply(interpretation, request.user_query)
            retrieval = self.planner.plan(enriched, request.user_query)
            response = self.answer_adapter.compose(request=request, retrieval=retrieval, started_at=started_at)
            return PipelineResponse(
                request_id=request_id,
                risk_level=response.risk_level,
                mode=response.mode,
                answer=response.answer,
                citations=response.citations,
                score=response.score,
                latency_ms=response.latency_ms,
                error=response.error,
                clarification=response.clarification,
                answer_plan=response.answer_plan,
            )
        except Exception as exc:  # noqa: BLE001
            return PipelineResponse(
                request_id=request_id,
                risk_level="HIGH",
                mode="error:Unhandled",
                answer="",
                citations={},
                score=0.0,
                latency_ms=(time.time() - started_at) * 1000.0,
                error={"stage": "Unhandled", "message": str(exc)},
            )
