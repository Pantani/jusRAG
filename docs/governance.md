# Governança

## Regras fundamentais do sistema

Estas regras são **obrigatórias em todos os módulos** (§2 da spec):

1. Nunca inventar artigo, lei, súmula, decisão, tese ou número de processo.
2. Toda afirmação jurídica relevante deve estar apoiada em uma fonte recuperada.
3. Quando não houver fonte suficiente, responder com **recusa segura**.
4. Separar claramente legislação, jurisprudência, interpretação e ressalvas.
5. Indicar quando a resposta depende de fatos adicionais.
6. Incluir aviso de que a resposta não é aconselhamento jurídico.
7. Manter fonte, URL, versão, data de ingestão e hash do conteúdo.
8. Escrever testes para lógica crítica.
9. Não colocar lógica de negócio dentro das rotas FastAPI.
10. Usar interfaces para embeddings, vector store, reranker e LLM provider.
11. Não commitar secrets, tokens, chaves de API ou dumps grandes.
12. Logs de perguntas devem ser anonimizáveis e desativáveis.
13. Testes não devem depender de rede externa por padrão.
14. Em ambiente local, usar dados seed pequenos e reproduzíveis.
15. A documentação deve explicar limitações, riscos e uso correto.

## Regras de segurança

- Não ingerir dados pessoais reais no seed.
- Não usar processos sigilosos.
- Não armazenar perguntas sensíveis sem opção de anonimização.
- Não expor stack traces ao usuário final.
- Não commitar API keys.
- Não prometer aconselhamento jurídico.
- Não permitir resposta sem fonte em temas jurídicos.

## Privacidade dos logs

Os run logs são controlados por configuração:

- `STORE_RUN_LOGS` — habilita/desabilita o armazenamento de logs de execução.
- `ANONYMIZE_RUN_LOGS` — anonimiza perguntas registradas.

Logs servem para observabilidade (`run_id` por execução, traces por etapa) sem reter dados sensíveis por padrão.

## Ownership e contratos

O projeto é construído por agentes de implementação com **ownership de arquivo disjunto**, coordenados por contratos validados em disco (Protocols de `EmbeddingProvider`, `VectorStore`, `AnswerWriter`, `CitationAuditor`). Arquivos compartilhados (`main.py`, `Makefile`, `README.md`, schemas) são coordenados, não editados ad hoc.

## Definition of Done

Uma fase está pronta quando: código + testes relevantes escritos e passando; lint/typing não pioram; docs atualizadas quando necessário; sem secrets; sem chamadas externas em testes unitários; os alvos `make` da fase funcionam; e os critérios de aceite da fase são atendidos.
