"""POST /ask — answer a legal question with cited sources (§20, §30).

No business logic here: the route validates the wire request and delegates to the
``AnswerService`` injected via dependencies, which drives the LangGraph runtime
(§14, ``packages.agents``). The response is the structured shape with mandatory
``sources`` and ``not_legal_advice=true``; questions without sufficient grounding
come back as a safe refusal (``status="refused"``) — out-of-scope questions are
caught up-front by the graph's ``LegalAreaClassifier`` (§15.2) rather than relying
on the prior semantic-score heuristic alone (AD-2 fix; mirrors AD-1 in
``ask-demo``).
"""

from __future__ import annotations

from fastapi import APIRouter

from apps.api.dependencies import AnswerServiceDep
from packages.answer.schemas import AnswerRequest, AnswerResponse

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AnswerResponse)
def ask(request: AnswerRequest, service: AnswerServiceDep) -> AnswerResponse:
    return service.ask(request.question, request.top_k, request.filters)
