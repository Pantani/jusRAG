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

## CDC integral (Lei 8.078/1990) — v1.2

A fonte seed do MVP é o **Código de Defesa do Consumidor (Lei 8.078/1990)**, texto oficial compilado do Planalto. Desde v1.2, o corpus é o **CDC integral**: 130 chunks (1 por artigo, do art. 1º ao 119, incluindo 42-A, 54-A..G, 104-A..C).

**Política de coleta:**

- Fonte: `https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm` (HTML oficial, encoding ISO-8859-1).
- **Vendored** em `data/seed/cdc/_source/planalto_l8078compilado.html` (uma única chamada de rede autorizada para baixar; após isso, ingestão é 100% offline).
- **SHA256** do HTML fixado no frontmatter de `cdc.md` como `fonte_html_hash:` para auditoria (§2 / §40.4).
- Loader `packages/ingestion/loaders/planalto_html.py` converte HTML→markdown de forma **determinística** (stdlib `html.parser`): preserva integralmente §, incisos, alíneas, marcações de tramitação ("Redação dada por…", "Vigência", "Vide", `(Vetado)`) — nada é removido.
- Pipeline: `apps/worker/jobs/ingest_cdc.py` regenera `cdc.md` a partir do HTML antes de chunkar; reingestão é idempotente por `content_hash`.

Cada chunk gerado preserva:

- `source = "planalto"`, `source_url` apontando para o texto oficial da lei;
- `norm_type = "lei"`, `norm_number = "8078"`, `norm_year = "1990"`, `article` (ex.: `12`);
- `version` (data da norma) e `content_hash` (`sha256:...`) do conteúdo normalizado;
- `legal_area = "consumer"`, `country = "BR"`, `jurisdiction = "federal"`, `is_current = true`.

O `chunk_id` é determinístico (ex.: `cdc-8078-1990-art-12`), o que torna a reingestão idempotente: rodar o job de novo sobre o mesmo conteúdo não duplica chunks.

## Jurisprudência STJ (v1.2)

A v1.2 amplia o seed de jurisprudência para **30 entradas** consumer-específicas:

- **15 súmulas STJ** — 130, 297, 302, 321, 359, 385, 404, 472, 477, 479, 532, 543, 595, 608, 632.
- **15 Temas repetitivos / recursos repetitivos** — 666, 717, 887, 932, 938, 939, 950, 952, 958, 960, 988, 990, 1006, 1020, 1030.

**Política de coleta:**

- Origem: sites oficiais STJ (`stj.jus.br/sumulasstj/` e `stj.jus.br/repetitivos-temas/`).
- **Recorte temático:** apenas conteúdo aplicável a Direito do Consumidor / CDC. Decisões de outras áreas ficam fora do seed.
- **Inclusões:** súmulas do STJ + Temas repetitivos com tese fixada.
- **Exclusões:** decisões monocráticas, processos sigilosos, conteúdo com PII. Acórdão individual entra apenas quando indicado como paradigma de Tema repetitivo.

**Política `needs_review`:** o campo `verification_status` no payload de cada chunk marca o estado da curadoria. Das 30 entradas atuais, **5 são `verified`** (`stj-sumula-130/297/302/479/543`) e **25 são `needs_review`**. Estas últimas foram redigidas de forma conservadora (sem inventar wording exato da tese, REsp paradigma ou data) e **precisam ser revisadas contra a fonte oficial antes do release v1.2 final**. Ver [docs/limitations.md](docs/limitations.md).

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
