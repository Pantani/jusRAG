# Limitações e não-objetivos

## Não é aconselhamento jurídico

O JusRAG Brasil **não presta aconselhamento jurídico**. É uma demonstração de arquitetura de pesquisa jurídica assistida por IA. Toda resposta carrega o aviso padrão:

> Esta resposta tem finalidade informativa e foi gerada com base nas fontes recuperadas pelo sistema. Ela não substitui a análise de um advogado ou profissional habilitado, especialmente porque a conclusão pode depender de fatos, documentos, datas e jurisprudência atualizada.

## Fora do escopo da v1

A v1 **não** implementa:

- Uma LLM treinada do zero.
- Cobertura completa de todo o direito brasileiro.
- Peticionamento automático em produção.
- Aconselhamento jurídico definitivo.
- Ingestão de processos sigilosos.
- Armazenamento de dados pessoais sensíveis de usuários.

## Limitações de escopo do MVP (v1.2)

- **Área única:** apenas Direito do Consumidor. Outras áreas (tributário, penal, trabalhista, família, sucessões, empresarial, administrativo, previdenciário, eleitoral) entram como **out-of-scope** no golden set e devem disparar recusa segura.
- **Recência.** O sistema responde com base no que foi ingerido; mudanças normativas posteriores à última ingestão não aparecem até nova ingestão. O CDC vendored é a versão compilada na data registrada no frontmatter (`fonte_html_hash` permite auditoria contra a fonte oficial).
- **Curadoria pendente da jurisprudência STJ.** Das **30 entradas** STJ (15 súmulas + 15 Temas repetitivos), **25 estão marcadas como `verification_status: "needs_review"`** no payload. O conteúdo foi escrito de forma conservadora (sem inventar wording da tese, REsp paradigma ou data) mas **precisa cross-check com a fonte oficial** (`stj.jus.br/sumulasstj/` e `stj.jus.br/repetitivos-temas/`) **antes do release v1.2 final**. As 5 entradas verified são `stj-sumula-130/297/302/479/543`.

## Limitações técnicas conhecidas

- **Sem garantia de completude:** o retrieval pode não trazer o artigo ideal; por isso há evals de recall.
- **Auditoria heurística:** a extração e verificação de claims é simples no MVP (Jaccard léxico com threshold calibrado por evidência); reduz, mas não elimina, claims sem suporte. A taxa é medida (`unsupported_legal_claim_rate`) e limitada por threshold.
- **Reranker opcional:** ausente ou básico na v1; a interface está preparada para evoluir.
- **Hybrid retrieval (semantic + BM25) ainda opt-in.** Disponível desde v1.2 via `ENABLE_HYBRID=true` + `docker compose --profile hybrid up`, com `FakeBM25Store` determinístico para testes. O `OpenSearchBM25Store` real é stub: falta plugar analyzer PT (`analysis-icu`/`analysis-nori` ou tokenizer/stemmer pt-br), tuning de heap, healthcheck e ranking calibrado em corpus de produção. Não usar em produção até a Fase 6 completa.
- **Embeddings PT vs EN.** Os embeddings disponíveis (OpenAI `text-embedding-3-small`, `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`) são treinados majoritariamente em **inglês**; recall de termos jurídicos específicos em português é inferior ao que se obteria com um modelo nativo pt-br (não há equivalente open production-grade no momento). Mitigação: hybrid retrieval com BM25 sobre vocabulário exato.

## Modo local (v1.1)

A partir da v1.1 o sistema roda 100% local via `EMBEDDING_PROVIDER=local` (sentence-transformers) + `LLM_PROVIDER=ollama`. Limitações específicas desse modo:

- **Capacidade do LLM.** Modelos 7–8B (`llama3.1:8b`, `qwen2.5:7b-instruct`) são significativamente menos capazes que LLMs cloud-tier (`gpt-4o-mini`, `gpt-4.1-mini`). Esperar: respostas menos articuladas, mais falhas em saída JSON estruturada exigida pelo `AnswerWriter`, e maior incidência de recusa segura quando o auditor reprova. Se `llama3.1:8b` falhar com frequência no parsing, tentar `qwen2.5:7b-instruct`.
- **Modelos pequenos (`llama3.2:1b`/`3b`) têm qualidade muito limitada para texto jurídico** — recusa segura é frequente, mas síntese e formatação JSON degradam rapidamente. Use apenas para sanity-check do pipeline.
- **`llama3.1:8b` em CPU é inviável sem GPU.** Latência ~30 s+ por `/ask` torna a UI Streamlit impraticável. Com GPU dedicada, ~3–8 s.
- **Latência.** OpenAI cloud entrega `/ask` em ~1–3 s. Ollama local em **CPU** fica tipicamente em **10–30 s** (8B+) ou **3–10 s** (1B–3B, qualidade limitada).
- **Embeddings.** `paraphrase-multilingual-mpnet-base-v2` (768d) tem qualidade decente em PT, porém **inferior** a `text-embedding-3-small` da OpenAI (1536d) em recall de termos jurídicos específicos.
- **Compatibilidade de collection Qdrant.** Dim 1536 (OpenAI) ≠ dim 768 (mpnet) ≠ dim 256 (fake) — **trocar provider exige recriar** a collection (`curl -X DELETE http://localhost:6333/collections/legal_chunks`) e reindexar. Não há migração in-place. O `make eval-real` faz pré-flight desse mismatch.
- **Regras invioláveis intactas.** §2/§40 — recusa segura, sem invenção de fontes, separação legislação/jurisprudência/ressalva — seguem aplicadas. O `CitationAuditor` é o gate; o provider de LLM é intercambiável.
- **Avaliação automática.** `make eval` continua rodando offline com **fake providers** determinísticos (CI reproduzível, sem dependência de modelos pesados). `make eval-real` cobre a medição manual com providers reais, mas **não roda em CI** por custo/latência/dependência externa.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Alucinação de fontes | Recuperação obrigatória + auditoria de citações + recusa segura. |
| Resposta fora de escopo | Classificador de área + recusa quando não há base. |
| Confiança indevida do usuário | Aviso de não aconselhamento em toda resposta e na UI. |
| Defasagem normativa | Versionamento por `content_hash` + reingestão idempotente. |
| Entrada STJ com tese incorreta | `verification_status` no payload; 25/30 entradas pendem revisão humana antes do release v1.2 final. |
