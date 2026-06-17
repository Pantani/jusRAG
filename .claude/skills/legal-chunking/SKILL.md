---
name: legal-chunking
description: >-
  Ingestão e chunking jurídico estrutural do jus-rag-brasil — chunking por estrutura normativa
  (artigo, parágrafo, inciso, alínea), hashing de conteúdo (content_hash), versionamento, idempotência
  de reingestão, loaders (markdown/HTML local, Planalto, LexML, STJ, STF) e geração de JSONL
  estruturado. Use ao implementar loaders, normalizer, chunker, versioning, o seed do CDC, a
  jurisprudência seed, ou os jobs ingest_cdc/index_cdc. A fonte normativa é o Prompt Master §5,8,18,22.
---

# Chunking e ingestão jurídica — jus-rag-brasil

Chunking jurídico não é por janela de tokens; é **por estrutura normativa**. Um artigo do CDC é a
unidade de citação verificável — o usuário precisa saber que a afirmação vem do art. 12, não de "um
trecho do documento". Quebrar por tamanho destruiria a rastreabilidade que é o ponto do projeto.

## Unidade de chunk

A unidade primária é o **artigo**. Quando o artigo é longo e tem estrutura interna relevante,
preserve `paragraph`, `inciso`, `alinea` nos metadados do chunk (campos de `LegalChunk`, ver skill
`legal-rag-contracts`). Cada chunk carrega a metadata jurídica completa para ser citável isoladamente:
`norm_type, norm_number, norm_year, article, source, source_url, version, content_hash`.

`chunk_id` segue convenção estável e legível, ex.: `cdc-8078-1990-art-12`. Estabilidade do id importa
para idempotência e para o `exact_citation_match` do ranking.

## CDC seed — §18

`data/seed/cdc/cdc.md` deve conter ao menos os artigos **6º, 12, 14, 18, 26 e 49**. O chunker detecta
a marcação de artigo ("Art. 12", "Art. 6º") e isola cada um. Aceite: esses artigos são detectados;
chunks preservam artigo, lei, fonte, versão e hash.

## content_hash e versionamento — §8

`content_hash = "sha256:" + sha256(texto_normalizado)`. O hash identifica unicamente o conteúdo de um
chunk/documento. **Reingestão é idempotente no nível de hash**: se o hash já existe, não reescreve nem
duplica. `version` é a data/rótulo da versão da norma (ex.: `2026-06-16`); permite distinguir redações
ao longo do tempo sem perder histórico.

**Por que hash + versão juntos:** o hash detecta mudança de conteúdo; a versão dá o eixo temporal
(`is_current`, vigência). Lei muda de redação — o sistema precisa saber qual redação sustentou uma
resposta dada no passado.

## Normalização

Normalize antes de hashear: unifique whitespace, normalize quebras, remova ruído de extração (cabeçalho/
rodapé de PDF/HTML). A normalização deve ser **determinística** — o mesmo input sempre gera o mesmo
hash, senão a idempotência quebra.

## Loaders — §5

Interface base em `packages/ingestion/loaders/base.py`. Implementações: `local_markdown.py` (MVP, CDC
seed), `local_html.py`, e stubs preparados para fontes oficiais `planalto.py`, `lexml.py`, `stj.py`,
`stf.py`. No MVP, jurisprudência começa por **loader local/seed** (`stj_consumer_seed.jsonl`) antes de
qualquer integração externa real — testes não dependem de rede (regra §13).

## Jurisprudência — §22

`CaseLawDocument` com chunking da **ementa**. Indexar com `doc_type="case_law"` (mesma collection ou
collection própria). Jurisprudência sem fonte recuperada **não é exibida** na resposta.

## Saída: JSONL estruturado

`make ingest-cdc` → `data/generated/cdc_chunks.jsonl`, um chunk por linha, cada um serializando um
`LegalChunk` completo. Esse JSONL é o contrato com o `index_cdc` (StorageAgent/retrieval): o indexador
lê o JSONL, gera embeddings e faz upsert no Qdrant. Não acoplar ingestão a embeddings — a fronteira é o
arquivo.

## Checklist de aceite da ingestão

- [ ] `make ingest-cdc` gera `data/generated/cdc_chunks.jsonl`.
- [ ] Artigos 6º, 12, 14, 18, 26, 49 detectados como chunks separados.
- [ ] Cada chunk tem `content_hash` e metadata jurídica completa.
- [ ] Reingestão não duplica (idempotência por hash).
- [ ] Normalização determinística (hash estável entre execuções).
