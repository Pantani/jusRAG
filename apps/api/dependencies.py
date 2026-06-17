"""FastAPI dependency providers.

Kept minimal for Phase 1. Downstream phases inject the embedding provider, vector
store, LLM provider and repositories here, always behind their `Protocol`s (§6 of
the system rules).

Since Phase 7, the HTTP ``/ask`` route is backed by the LangGraph runtime
(``packages.agents``), not the standalone ``AnswerWriter``. The
``AnswerService`` exposed here is a thin adapter that drives the compiled graph
with the *same* DI-selected providers (embedding + vector store + LLM) and maps
the resulting ``LegalResearchState`` into the public ``AnswerResponse`` shape
(short_answer, legal_basis[], case_law[], caveats[], sources[],
not_legal_advice=true, audit, status). The robust scope gate from the graph
(``LegalAreaClassifier``, §15.2) replaces the writer's fragile semantic-score
heuristic, so out-of-scope questions now refuse safely on the HTTP path too
(AD-2 fix; AD-1 fixed the same showcase in ``ask-demo``).
"""

from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends

from packages.agents.answer_writer import AnswerBuffer
from packages.agents.graph import build_graph
from packages.agents.state import (
    CitationAuditResult as StateAuditResult,
)
from packages.agents.state import (
    LegalResearchState,
)
from packages.answer.formatter import build_refusal
from packages.answer.schemas import (
    AnswerResponse,
    AnswerStatus,
    CitationAudit,
)
from packages.config.settings import Settings, get_settings
from packages.embeddings.base import EmbeddingProvider
from packages.embeddings.selector import embedding_vector_size, make_embedding_provider
from packages.llm.base import LLMProvider
from packages.llm.selector import make_llm_provider
from packages.rag.context_builder import BuiltContext
from packages.rag.retriever import LegalRetriever
from packages.rag.search_service import SearchService
from packages.storage.base import VectorStore
from packages.storage.qdrant import QdrantVectorStore

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_embedding_provider(settings: SettingsDep) -> EmbeddingProvider:
    """Configured embedding provider (§: EMBEDDING_PROVIDER).

    ``fake`` returns the deterministic, network-free provider (offline/demo, no
    ``OPENAI_API_KEY`` required); ``openai`` returns the real provider, which still
    raises explicitly when the key is missing (no silent fallback). Overridden by
    the fake in unit tests regardless of settings.
    """

    return make_embedding_provider(settings)


def get_vector_store(settings: SettingsDep) -> VectorStore:
    """Real Qdrant store. Overridden by the in-memory store in tests.

    The collection vector size must match the *selected* embedding provider's
    dimensionality (1536 for OpenAI, the fake provider's ``dim`` otherwise);
    switching providers on an existing collection requires recreating it.
    """

    return QdrantVectorStore(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection_legal_chunks,
        vector_size=embedding_vector_size(settings),
    )


EmbeddingProviderDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
VectorStoreDep = Annotated[VectorStore, Depends(get_vector_store)]


def get_search_service(embeddings: EmbeddingProviderDep, store: VectorStoreDep) -> SearchService:
    return SearchService(LegalRetriever(embeddings, store))


SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]


def get_llm_provider(settings: SettingsDep) -> LLMProvider:
    """Configured LLM provider (§: LLM_PROVIDER).

    ``fake`` returns the deterministic, network-free provider (offline /ask, no
    ``OPENAI_API_KEY`` required); ``openai`` returns the real provider, which still
    raises explicitly when the key is missing (no silent fallback). Overridden by
    the fake in unit tests regardless of settings.
    """

    return make_llm_provider(settings)


LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]


class AnswerService:
    """Graph-backed answer pipeline behind POST /ask (§14, §20).

    Builds the compiled §14 graph from the injected ``SearchService`` and
    ``LLMProvider`` and exposes a single ``ask`` entry point that returns the
    public ``AnswerResponse`` shape. State threading uses a fresh per-request
    ``run_id`` (uuid4) so concurrent requests stay isolated in the per-run
    ``AnswerBuffer``.

    The graph is compiled once per service instance: ``StateGraph.compile`` is
    pure (no I/O), the per-run state is passed explicitly to ``invoke``, and
    the buffer/collector instances we hold are written to keyed by ``run_id``,
    so reuse across requests is safe.
    """

    def __init__(self, search: SearchService, llm: LLMProvider) -> None:
        self._buffer = AnswerBuffer()
        self._app = build_graph(search=search, llm=llm, buffer=self._buffer)

    def ask(
        self,
        question: str,
        top_k: int = 8,  # noqa: ARG002  # graph governs retrieval depth (§14)
        filters: dict[str, Any] | None = None,  # noqa: ARG002  # graph applies scope filters
    ) -> AnswerResponse:
        """Drive the graph for one question and map the result to the wire shape.

        Note: ``top_k`` and ``filters`` are accepted for wire-shape stability but
        the LangGraph runtime owns retrieval depth (per-researcher ``top_k=8``)
        and scope filtering (``LegalAreaClassifier`` + per-block ``doc_type``).
        Threading the request-level ``top_k``/``filters`` through every node
        would couple the route to graph internals — left out by design (§14).
        """

        run_id = uuid4().hex
        initial = LegalResearchState(
            run_id=run_id, question=question, jurisdiction="BR"
        )
        state = LegalResearchState.model_validate(self._app.invoke(initial))
        buffered = self._buffer.answer(run_id)
        return _to_answer_response(state, buffered)


def _to_answer_response(
    state: LegalResearchState, buffered: AnswerResponse | None
) -> AnswerResponse:
    """Map ``LegalResearchState`` + buffered answer to the public shape (§30).

    Two cases:
      (a) Buffered answer exists (synthesis ran): keep its short_answer /
          legal_basis / case_law / sources; overlay caveats and status from the
          final state; attach the §13 audit translated to the §31 wire field
          names (``unsupported_claim_rate`` → ``unsupported_legal_claim_rate``).
      (b) No buffered answer (refusal before synthesis: out-of-scope, needs
          more info): return the safe refusal with empty context, status from
          state, and ``audit=None`` — never invent an audit verdict.
    """

    status = _map_status(state.status)
    if buffered is not None:
        return buffered.model_copy(
            update={
                "status": status,
                "caveats": list(state.caveats),
                "audit": _audit_from_state(state.audit),
            }
        )
    refusal = build_refusal(BuiltContext(text="", citations=[], chunks=[]))
    return refusal.model_copy(
        update={"status": status, "caveats": list(state.caveats), "audit": None}
    )


def _map_status(status: str) -> AnswerStatus:
    """Project the §13 closed-set status onto the wire enum (§30).

    The wire shape only distinguishes ``answered`` vs ``refused`` (§30). Any
    non-``answered`` runtime status (``refused``, ``needs_more_info``,
    ``failed``, residual ``running``) collapses to ``refused`` on the wire —
    we never expose a half-finished answer as ``answered``.
    """

    return AnswerStatus.ANSWERED if status == "answered" else AnswerStatus.REFUSED


def _audit_from_state(audit: StateAuditResult | None) -> CitationAudit | None:
    if audit is None:
        return None
    return CitationAudit(
        citation_coverage=audit.citation_coverage,
        unsupported_legal_claim_rate=audit.unsupported_claim_rate,
        unsupported_claims=list(audit.unsupported_claims),
        passed=audit.passed,
    )


def get_answer_service(service: SearchServiceDep, llm: LLMProviderDep) -> AnswerService:
    return AnswerService(service, llm)


AnswerServiceDep = Annotated[AnswerService, Depends(get_answer_service)]

__all__ = [
    "AnswerService",
    "AnswerServiceDep",
    "EmbeddingProviderDep",
    "LLMProviderDep",
    "SearchServiceDep",
    "SettingsDep",
    "VectorStoreDep",
    "get_answer_service",
    "get_embedding_provider",
    "get_llm_provider",
    "get_search_service",
    "get_settings",
    "get_vector_store",
]
