# Política de fontes

## Princípio

Toda afirmação jurídica relevante deve estar apoiada em uma **fonte oficial recuperada**. O sistema nunca inventa artigo, lei, súmula, decisão, tese ou número de processo. Quando não há fonte suficiente, a resposta é uma **recusa segura**.

## Fontes oficiais aceitas

| Fonte | Tipo | Uso |
|---|---|---|
| **Planalto** (planalto.gov.br) | Legislação federal | Texto oficial de leis (ex.: CDC, Lei 8.078/1990). |
| **LexML** (lexml.gov.br) | Legislação e metadados | Identificação e versionamento normativo. |
| **STJ** | Jurisprudência | Acórdãos, súmulas e teses repetitivas. |
| **STF** | Jurisprudência | Súmulas vinculantes, repercussão geral. |

No MVP, as fontes entram como **seed local** (ex.: `data/seed/cdc/cdc.md`), reproduzível e sem dados pessoais reais nem processos sigilosos. Loaders dedicados (`planalto`, `lexml`, `stj`, `stf`) são preparados para ingestão a partir das origens oficiais nas fases seguintes.

## CDC seed (Lei 8.078/1990)

A fonte seed do MVP é o **Código de Defesa do Consumidor (Lei 8.078/1990)**, cujo texto oficial é o do Planalto (`planalto.gov.br`). O seed cobre os artigos **6º, 12, 14, 18, 26 e 49**, fatiados por artigo (uma unidade citável por artigo). Cada chunk gerado preserva:

- `source = "planalto"`, `source_url` apontando para o texto oficial da lei;
- `norm_type = "lei"`, `norm_number = "8078"`, `norm_year = "1990"`, `article` (ex.: `12`);
- `version` (data da norma) e `content_hash` (`sha256:...`) do conteúdo normalizado;
- `legal_area = "consumer"`, `country = "BR"`, `jurisdiction = "federal"`, `is_current = true`.

O `chunk_id` é determinístico (ex.: `cdc-8078-1990-art-12`), o que torna a reingestão idempotente: rodar o job de novo sobre o mesmo conteúdo não duplica chunks.

## Persistência obrigatória

Para todo documento e chunk, persistir:

- **source** — origem (ex.: `planalto`, `stj`).
- **source_url** — URL oficial verificável.
- **version** — versão/data da norma (ex.: `2026-06-16`).
- **ingestion_date** — data de ingestão.
- **content_hash** — `sha256:...` do conteúdo normalizado.

Exemplo de payload (legislação) no vector DB:

```json
{
  "doc_type": "statute",
  "source": "planalto",
  "legal_area": "consumer",
  "country": "BR",
  "jurisdiction": "federal",
  "norm_type": "lei",
  "norm_number": "8078",
  "norm_year": "1990",
  "article": "12",
  "is_current": true,
  "version": "2026-06-16",
  "source_url": "...",
  "content_hash": "sha256:..."
}
```

Para jurisprudência, o payload adiciona `court`, `case_number`, `rapporteur`, `panel`, `judgment_date`, `publication_date`, `precedent_type` e `is_binding`.

## Idempotência

A reingestão é **idempotente no nível do `content_hash`**: documentos cujo conteúdo não mudou não geram chunks ou vetores duplicados. Mudanças normativas produzem nova `version`, preservando o histórico (versionamento jurídico).

## Restrições

- Não ingerir dados pessoais reais no seed.
- Não usar processos sigilosos.
- Não commitar dumps grandes nem secrets.
- Jurisprudência sem fonte verificável **não é exibida**.
