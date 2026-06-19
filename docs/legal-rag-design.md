# Desenho do Legal RAG

## Por que a arquitetura é o diferencial, não o LLM

Um LLM bom escreve texto jurídico convincente, mas não tem garantia de veracidade: pode alucinar artigos, súmulas, números de processo e teses. Trocar de modelo melhora a fluência, **não** a confiabilidade. O valor do JusRAG Brasil está na arquitetura ao redor do modelo, que impõe verificabilidade em cada etapa:

```text
fonte → recuperação → ranking → síntese → auditoria → ressalva → avaliação
```

Cada etapa é uma barreira contra alucinação:

1. **Fonte** — só material oficial e versionado entra no índice (ver [source-policy.md](source-policy.md)).
2. **Recuperação** — vector search (Qdrant) com filtros de metadata, BM25 opcional e roteamento por tipo de documento (statute / case_law).
3. **Ranking** — scoring composto que combina similaridade semântica com **autoridade jurídica**.
4. **Síntese** — o Answer Writer só pode usar o contexto recuperado; separa legislação, jurisprudência e ressalvas.
5. **Auditoria** — o Citation Auditor verifica cada claim contra o contexto e mede cobertura.
6. **Ressalva** — toda resposta carrega o aviso de não aconselhamento; respostas sem base suficiente são recusadas.
7. **Avaliação** — evals medem recall, cobertura de citação e taxa de claims sem suporte (ver [evaluation.md](evaluation.md)).

## Chunking jurídico

Diferente de chunking genérico por tokens, o chunking é **por estrutura normativa** — tipicamente por artigo. Isso mantém a unidade citável coerente (um artigo, um parágrafo) e permite citação precisa (`art. 12`, `art. 49`). O pipeline é `loader → normalizer → chunker → versioning → JSONL` (ver [architecture.md](architecture.md)).

Cada chunk é um `LegalChunk` (§8) com metadata jurídica que sustenta filtros de retrieval e citação verificável: `chunk_id` determinístico, `article`/`paragraph`/`inciso`/`alinea`, `norm_type`/`norm_number`/`norm_year`, `legal_area`, `source`/`source_url`, `version` e `content_hash`. Essa metadata vira o payload do vector DB (§9) e alimenta o `legal_authority` (via `hierarchy.py`) usado no ranking abaixo.

## Ranking jurídico

O score combina relevância semântica com **autoridade da fonte**. No MVP (antes de BM25):

```text
final_score = 0.70 * semantic_similarity
            + 0.20 * legal_authority
            + 0.10 * exact_citation_match
```

Versão completa (com BM25):

```text
final_score = 0.30 * semantic_similarity
            + 0.20 * bm25_score
            + 0.15 * legal_authority
            + 0.10 * binding_weight
            + 0.10 * recency
            + 0.10 * exact_citation_match
            + 0.05 * source_quality
```

### Pesos de autoridade

| Fonte | Peso |
|---|---|
| Constituição Federal | 1.00 |
| Lei federal vigente | 0.95 |
| Súmula vinculante | 0.95 |
| STF repercussão geral | 0.95 |
| STJ recurso repetitivo | 0.90 |
| STJ súmula | 0.88 |
| STJ acórdão comum | 0.75 |
| TJ estadual | 0.60 |
| Doutrina | 0.40 |
| Blog/artigo | 0.20 |
| Fonte desconhecida | 0.10 |

## Saídas estruturadas

O Answer Writer produz uma forma estruturada e auditável:

```json
{ short_answer, legal_basis[], case_law[], caveats[], sources[], not_legal_advice: true }
```

O Citation Auditor produz:

```json
{ citation_coverage, unsupported_legal_claim_rate, unsupported_claims[], passed }
```

Separar **legislação**, **jurisprudência**, **interpretação** e **ressalvas** é parte do desenho — não um detalhe de formatação. É o que permite ao usuário verificar cada afirmação contra a fonte citada.
