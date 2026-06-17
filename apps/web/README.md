# apps/web — Demo Streamlit

Interface de demonstração do JusRAG Brasil. **Apenas apresentação**: consome o endpoint
`POST /ask` da API e renderiza a `AnswerResponse` estruturada. Nenhuma lógica de negócio
jurídica vive aqui (§12.12).

## O que a UI exibe (§25)

- campo de **pergunta**;
- **resposta** sintetizada (`short_answer`);
- **fundamento legal** (legislação) e **jurisprudência** em cards **separados** (§2.3);
- **fontes / chunks usados** em cards, com `doc_type`, `source`, `chunk_id` e URL oficial;
- **ressalvas** (caveats);
- **audit score** (`citation_coverage`, `unsupported_legal_claim_rate`, `passed`), com
  destaque visual quando `passed=false`;
- **aviso de não aconselhamento jurídico** (§41) sempre visível e proeminente;
- **recusa segura** (`status="refused"`) sinalizada claramente.

Erros de conexão com a API geram mensagem clara, nunca stack trace.

## Como rodar

A API precisa estar no ar com a collection indexada (ver `docs/demo-script.md`).

```bash
pip install -e ".[demo]"
JUSRAG_API_URL=http://localhost:8000 streamlit run apps/web/app.py
```

`JUSRAG_API_URL` é configurável (default `http://localhost:8000`).
