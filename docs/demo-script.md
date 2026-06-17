# Roteiro de demo

Roteiro real para demonstrar o JusRAG Brasil ponta a ponta: subir o stack, indexar as
fontes seed, rodar a API e a UI Streamlit, e fazer perguntas de exemplo. A UI consome o
endpoint `/ask` existente — **apenas apresentação**, sem lógica de negócio jurídica.

> **Aviso de não aconselhamento jurídico** — Esta demo tem finalidade informativa. As
> respostas não substituem a análise de um advogado ou profissional habilitado (§41).

## 1. Subir o stack

```bash
cp .env.example .env      # ajuste OPENAI_API_KEY se for usar provider real
make up                   # docker compose up --build (api, postgres, qdrant, redis)
```

Healthcheck:

```bash
curl http://localhost:8000/health    # -> {"status": "ok"}
```

## 2. Indexar as fontes seed

```bash
make ingest-cdc           # CDC (Lei 8.078/1990): arts. 6º, 12, 14, 18, 26, 49
make ingest-case-law      # Súmulas do STJ (consumer): 297, 302, 130, 479, 543
make index-cdc            # indexa statute + case_law na collection Qdrant legal_chunks
```

`index-cdc` carrega `cdc_chunks.jsonl` e, quando presente, `case_law_chunks.jsonl` na mesma
collection `legal_chunks`. A indexação é idempotente por `chunk_id`.

## 3. (Opcional) Validar pela linha de comando

```bash
make search-demo          # busca semântica
make ask-demo             # resposta citada via pipeline /ask
make eval                 # suíte de evals → data/generated/eval_report.{json,md}
```

## 4. Rodar a UI

A API do passo 1 precisa estar no ar com a collection indexada (passo 2).

```bash
pip install -e ".[demo]"
JUSRAG_API_URL=http://localhost:8000 streamlit run apps/web/app.py
```

A UI abre em `http://localhost:8501`. Para cada pergunta ela exibe: resposta, fundamento
legal e jurisprudência em cards **separados**, fontes/chunks usados, ressalvas, audit score
(com destaque quando reprova) e o aviso de não aconselhamento.

## 5. Perguntas de exemplo

As três perguntas abaixo exercitam legislação, jurisprudência e recusa segura. Os números
de artigo/súmula correspondem ao seed real — a UI nunca inventa fontes.

### a) Defeito do produto → CDC art. 12

> **Pergunta:** "O fornecedor responde por defeito que torna o produto perigoso?"

Esperado na tela:
- **resposta** descrevendo a responsabilidade do fornecedor pelo fato do produto;
- **fundamento legal** citando o **art. 12** do CDC, com `chunk_id` `cdc-8078-1990-art-12`;
- **fontes** com URL do Planalto;
- **audit** com cobertura alta e `passed = true`.

### b) Direito de arrependimento → CDC art. 49

> **Pergunta:** "Comprei um produto pela internet e me arrependi. Posso desistir?"

Esperado na tela:
- **resposta** sobre o direito de arrependimento em compras fora do estabelecimento;
- **fundamento legal** citando o **art. 49** do CDC (prazo de 7 dias);
- **fontes** com URL do Planalto e `passed = true` no audit.

### c) CDC aplica-se a banco → STJ Súmula 297

> **Pergunta:** "O Código de Defesa do Consumidor se aplica aos bancos?"

Esperado na tela:
- **resposta** afirmando a aplicação do CDC às instituições financeiras;
- bloco de **jurisprudência** (separado da legislação) com a **Súmula 297 do STJ**,
  `chunk_id` `stj-sumula-297`, court `STJ`, com URL de fonte;
- **audit** validando a citação da súmula.

### d) Fora do escopo → recusa segura

> **Pergunta:** "Qual a pena para furto qualificado no Código Penal?"

Esperado na tela:
- **recusa segura** sinalizada claramente (`status = refused`): sem fontes de Direito do
  Consumidor que sustentem a resposta, o sistema recusa em vez de arriscar (§2.2).

> Os exemplos refletem o comportamento real do sistema sobre o seed; os textos exatos da
> resposta dependem do `LLMProvider` configurado (fake determinístico ou OpenAI).
