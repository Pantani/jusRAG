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

## Limitações de escopo do MVP

- **Área única:** apenas Direito do Consumidor.
- **Fonte seed restrita:** CDC (Lei 8.078/1990), artigos 6º, 12, 14, 18, 26 e 49. Perguntas fora desse recorte tendem a **recusa segura** — comportamento esperado, não falha.
- **Jurisprudência inicial:** seed STJ pequeno (súmulas 130, 297, 302, 479 e 543); não reflete toda a jurisprudência consolidada.
- **Recência:** o sistema responde com base no que foi ingerido; mudanças normativas posteriores à ingestão não aparecem até nova ingestão.

## Limitações técnicas conhecidas

- **Sem garantia de completude:** o retrieval pode não trazer o artigo ideal; por isso há evals de recall.
- **Auditoria heurística:** a extração e verificação de claims é simples no MVP; reduz, mas não elimina, claims sem suporte. A taxa é medida (`unsupported_legal_claim_rate`) e limitada por threshold.
- **Reranker opcional:** ausente ou básico na v1; a interface está preparada para evoluir.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Alucinação de fontes | Recuperação obrigatória + auditoria de citações + recusa segura. |
| Resposta fora de escopo | Classificador de área + recusa quando não há base. |
| Confiança indevida do usuário | Aviso de não aconselhamento em toda resposta e na UI. |
| Defasagem normativa | Versionamento por `content_hash` + reingestão idempotente. |
