"""POST /ask — answer a legal question with cited sources (§20, §30).

No business logic here: the route validates the wire request and delegates to the
``AnswerWriter`` injected via dependencies. The response is the structured shape
with mandatory ``sources`` and ``not_legal_advice=true``; questions without
sufficient grounding come back as a safe refusal (``status="refused"``).
"""

from __future__ import annotations

from fastapi import APIRouter

from apps.api.dependencies import AnswerWriterDep
from packages.answer.schemas import AnswerRequest, AnswerResponse

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AnswerResponse)
def ask(request: AnswerRequest, writer: AnswerWriterDep) -> AnswerResponse:
    return writer.write(request.question, request.top_k, request.filters)
