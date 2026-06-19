"""Streamlit demo UI for JusRAG Brasil (§25, §12.12).

Presentation only — no legal business logic here. The app sends the question to the
existing ``POST /ask`` endpoint and renders the structured ``AnswerResponse``: the
synthesized answer, sources as cards (legislation and case-law kept visibly separate,
§2.3), the retrieved chunks, the caveats, the citation-audit score, and the mandatory
non-advice disclaimer (§41). Safe refusals (``status="refused"``) and API connection
errors are shown clearly, never as a stack trace.

Run with::

    JUSRAG_API_URL=http://localhost:8000 streamlit run apps/web/app.py
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st

DEFAULT_API_URL = "http://localhost:8000"
REQUEST_TIMEOUT_S = 60.0

# §41 — texto de limitação padrão (sempre visível e proeminente).
NON_ADVICE_DISCLAIMER = (
    "Esta resposta tem finalidade informativa e foi gerada com base nas fontes "
    "recuperadas pelo sistema. Ela não substitui a análise de um advogado ou "
    "profissional habilitado, especialmente porque a conclusão pode depender de "
    "fatos, documentos, datas e jurisprudência atualizada."
)


def api_base_url() -> str:
    """Resolve the API base URL from the environment (configurable, no secrets)."""
    return os.environ.get("JUSRAG_API_URL", DEFAULT_API_URL).rstrip("/")


def call_ask(question: str, top_k: int, base_url: str) -> dict[str, Any]:
    """Call ``POST /ask`` and return the parsed JSON, raising for HTTP errors."""
    response = httpx.post(
        f"{base_url}/ask",
        json={"question": question, "top_k": top_k},
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    return payload


def render_disclaimer() -> None:
    """Render the non-advice disclaimer (§41) prominently."""
    st.warning(f"**Aviso de não aconselhamento jurídico** — {NON_ADVICE_DISCLAIMER}", icon="⚠️")


def render_audit(audit: dict[str, Any] | None) -> None:
    """Render the citation-audit score, highlighting a failed audit."""
    st.subheader("Auditoria de citações")
    if audit is None:
        st.info("Sem auditoria disponível para esta resposta.")
        return

    coverage = audit.get("citation_coverage", 0.0)
    unsupported = audit.get("unsupported_legal_claim_rate", audit.get("unsupported_rate", 0.0))
    passed = bool(audit.get("passed", False))

    col_cov, col_uns, col_status = st.columns(3)
    col_cov.metric("Cobertura de citação", f"{coverage:.0%}")
    col_uns.metric("Claims sem suporte", f"{unsupported:.0%}")
    col_status.metric("Status", "passou" if passed else "falhou")

    if not passed:
        st.error(
            "Auditoria **reprovou**: a resposta contém afirmações sem suporte nas "
            "fontes recuperadas. Trate o resultado com cautela.",
            icon="🚨",
        )

    unsupported_claims = audit.get("unsupported_claims") or []
    if unsupported_claims:
        with st.expander(f"Claims sem suporte ({len(unsupported_claims)})"):
            for claim in unsupported_claims:
                st.write(f"- {claim}")


def render_legal_basis(legal_basis: list[dict[str, Any]]) -> None:
    """Render the legislation-grounded statements (separate from case-law, §2.3)."""
    if not legal_basis:
        return
    st.subheader("Fundamento legal (legislação)")
    for item in legal_basis:
        with st.container(border=True):
            st.markdown(item.get("text", ""))
            citations = item.get("citations") or []
            if citations:
                st.caption("Citações: " + ", ".join(citations))


def _render_case_law_card(item: dict[str, Any]) -> None:
    with st.container(border=True):
        header_parts = [p for p in (item.get("court"), item.get("case_number")) if p]
        if header_parts:
            st.markdown("**" + " — ".join(header_parts) + "**")
        st.markdown(f"*{item.get('title', '')}*")
        ementa = item.get("ementa")
        if ementa:
            st.write(ementa)
        source_url = item.get("source_url")
        if source_url:
            st.markdown(f"[Fonte]({source_url})")


def render_case_law(case_law: list[dict[str, Any]]) -> None:
    """Render jurisprudence cards, clearly separated from legislation (§2.3, §22)."""
    if not case_law:
        return
    st.subheader("Jurisprudência relevante")
    for item in case_law:
        _render_case_law_card(item)


def _render_source_card(item: dict[str, Any]) -> None:
    with st.container(border=True):
        title = item.get("title", "")
        article = item.get("article")
        heading = f"{title} — {article}" if article else title
        st.markdown(f"**{heading}**")
        badges = [b for b in (item.get("doc_type"), item.get("source")) if b]
        if badges:
            st.caption(" · ".join(badges) + f" · `{item.get('chunk_id', '')}`")
        source_url = item.get("source_url")
        if source_url:
            st.markdown(f"[Fonte oficial]({source_url})")


def render_sources(sources: list[dict[str, Any]]) -> None:
    """Render the consulted sources / retrieved chunks as cards."""
    if not sources:
        return
    st.subheader("Fontes e chunks usados")
    for item in sources:
        _render_source_card(item)


def render_caveats(caveats: list[str]) -> None:
    """Render the answer caveats (ressalvas)."""
    if not caveats:
        return
    st.subheader("Ressalvas")
    for caveat in caveats:
        st.markdown(f"- {caveat}")


def render_answer(payload: dict[str, Any]) -> None:
    """Render the full structured AnswerResponse."""
    status = payload.get("status")
    if status == "refused":
        st.error(
            "**Recusa segura.** O sistema não encontrou base suficiente nas fontes "
            "recuperadas para responder, então recusou em vez de arriscar uma resposta "
            "sem fundamento (§2.2).",
            icon="🛑",
        )
        if payload.get("short_answer"):
            st.write(payload["short_answer"])
    else:
        st.subheader("Resposta")
        st.markdown(payload.get("short_answer", ""))

    render_legal_basis(payload.get("legal_basis") or [])
    render_case_law(payload.get("case_law") or [])
    render_sources(payload.get("sources") or [])
    render_caveats(payload.get("caveats") or [])
    render_audit(payload.get("audit"))


def main() -> None:
    st.set_page_config(page_title="JusRAG Brasil — Demo", page_icon="⚖️", layout="centered")
    st.title("⚖️ JusRAG Brasil")
    st.caption(
        "Copiloto de pesquisa jurídica (Direito do Consumidor — CDC) com citações "
        "verificáveis e auditoria de claims. Demo conectada ao endpoint /ask."
    )

    render_disclaimer()

    base_url = api_base_url()
    with st.sidebar:
        st.header("Configuração")
        st.write(f"API: `{base_url}`")
        st.caption("Defina `JUSRAG_API_URL` para apontar para outra instância.")
        top_k = st.slider("top_k (fontes recuperadas)", min_value=1, max_value=20, value=8)

    question = st.text_input(
        "Pergunta jurídica",
        placeholder="Ex.: O fornecedor responde por defeito do produto?",
    )

    if not st.button("Perguntar", type="primary"):
        return

    if not question.strip():
        st.info("Digite uma pergunta para começar.")
        return

    with st.spinner("Consultando fontes e sintetizando resposta..."):
        try:
            payload = call_ask(question.strip(), top_k, base_url)
        except httpx.ConnectError:
            st.error(
                f"Não foi possível conectar à API em `{base_url}`. Verifique se ela "
                "está rodando (`make up`) e se `JUSRAG_API_URL` está correto.",
                icon="🔌",
            )
            return
        except httpx.HTTPStatusError as exc:
            st.error(
                f"A API respondeu com erro {exc.response.status_code}. "
                "Verifique os logs do serviço.",
                icon="❌",
            )
            return
        except httpx.HTTPError:
            st.error(
                "Falha de comunicação com a API. Verifique a conexão e tente novamente.",
                icon="❌",
            )
            return

    render_answer(payload)


if __name__ == "__main__":
    main()
