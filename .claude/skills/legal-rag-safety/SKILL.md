---
name: legal-rag-safety
description: >-
  Regras de segurança jurídica e correção do jus-rag-brasil — proibição de inventar fontes, recusa
  segura quando não há base, separação legislação/jurisprudência/ressalva, aviso de não aconselhamento,
  prompts do AnswerWriter/CitationAuditor/RiskChecker, ranking jurídico com pesos de autoridade, e
  regras de governança. Use ao redigir respostas, auditar citações, checar riscos, montar prompts de
  LLM, implementar ranking, ou qualquer ponto que decida o que o sistema afirma ao usuário. A fonte
  normativa é o Prompt Master §2,32-34,38-41.
---

# Segurança e correção jurídica — jus-rag-brasil

O diferencial do projeto não é a LLM "responder bem"; é a arquitetura **obrigar** a resposta a passar
por fonte → recuperação → ranking → síntese → auditoria → ressalva → avaliação. Estas regras tornam
isso executável. Elas bindam todos os módulos que produzem texto para o usuário.

## Regras fundamentais — §2 / §40

1. Nunca inventar artigo, lei, súmula, decisão, tese ou número de processo.
2. Toda afirmação jurídica relevante deve estar apoiada em uma fonte recuperada.
3. Sem fonte suficiente → **recusa segura** (não responder o mérito).
4. Separar claramente legislação, jurisprudência, interpretação e ressalvas.
5. Indicar quando a resposta depende de fatos/provas/documentos adicionais.
6. Incluir sempre o aviso de não aconselhamento jurídico.
7. Manter fonte, URL, versão, data de ingestão e `content_hash`.
8. Não colocar lógica de negócio nas rotas FastAPI.
9. Sem dados pessoais reais ou processos sigilosos no seed; sem secrets commitados; sem stack trace
   ao usuário final; logs de perguntas anonimizáveis e desativáveis.

**Por que recusa em vez de "melhor esforço":** em direito, uma resposta convincente e errada (artigo
inexistente, súmula inventada) é pior que admitir falta de base. O custo de um falso positivo é alto;
a recusa é o comportamento seguro padrão.

## Aviso de limitação padrão — §41

Anexar a toda resposta:

> Esta resposta tem finalidade informativa e foi gerada com base nas fontes recuperadas pelo sistema.
> Ela não substitui a análise de um advogado ou profissional habilitado, especialmente porque a
> conclusão pode depender de fatos, documentos, datas e jurisprudência atualizada.

## Prompt do AnswerWriter — §32

```
Você é um redator jurídico assistivo para um sistema de pesquisa jurídica brasileira.
Responda em português brasileiro.
Use exclusivamente as fontes fornecidas no CONTEXTO.
Não invente artigos, leis, súmulas, decisões, teses ou números de processo.
Toda afirmação jurídica relevante deve estar apoiada em uma fonte do contexto.
Se o contexto não sustentar uma conclusão, diga que não há base suficiente.
Não forneça aconselhamento jurídico definitivo.
Use linguagem clara, técnica e conservadora.

Formato obrigatório:
1. Resposta curta
2. Fundamento legal
3. Jurisprudência relevante, se houver
4. Ressalvas e limites
5. Fontes consultadas
6. Aviso: esta resposta é informativa e não substitui análise de advogado.
```

## Prompt do CitationAuditor — §33

```
Você é um auditor de citações jurídicas.
Verifique se a resposta está totalmente suportada pelas fontes recuperadas:
- Toda afirmação jurídica relevante tem fonte?
- A fonte citada existe no contexto?
- O artigo citado corresponde ao conteúdo?
- A resposta extrapola a fonte?
- Há linguagem absoluta indevida?
- A resposta inventa jurisprudência, súmula, tese ou número de processo?
Retorne: claims suportados, claims sem suporte, citation_coverage,
unsupported_legal_claim_rate, passed true/false.
Se houver claim sem suporte, recomende remover ou qualificar a afirmação.
```

## Prompt do RiskChecker — §34

```
Você é um agente de risco e limitação jurídica.
Revise a resposta final para garantir que:
- Não pareça aconselhamento jurídico definitivo.
- Indique quando faltam fatos relevantes.
- Indique quando a conclusão depende de prova, documentos ou contexto.
- Indique que a resposta é informativa.
- Evite termos absolutos ("sempre", "nunca", "garantido"), exceto quando a fonte sustentar claramente.
```

## Classificação de área (MVP) — §15.2

Áreas: `consumer, civil, labor, constitutional, tax, criminal, administrative, unknown`. Regra MVP:
se não for `consumer`, avisar que a base atual cobre principalmente direito do consumidor, mas ainda
pode pesquisar fontes genéricas se disponíveis.

## Ranking jurídico — §38

MVP (sem BM25 ainda):
`final_score = 0.70·semantic_similarity + 0.20·legal_authority + 0.10·exact_citation_match`

Completo (quando houver BM25):
`0.30·semantic + 0.20·bm25 + 0.15·legal_authority + 0.10·binding_weight + 0.10·recency
+ 0.10·exact_citation_match + 0.05·source_quality`

## Pesos de autoridade — §39

Constituição 1.00 · lei federal vigente 0.95 · súmula vinculante 0.95 · STF repercussão geral 0.95 ·
STJ repetitivo 0.90 · STJ súmula 0.88 · STJ acórdão comum 0.75 · TJ estadual 0.60 · doutrina 0.40 ·
blog/artigo 0.20 · fonte desconhecida 0.10.

## Roteamento de risco no grafo — §14

- Fora do escopo e sem fonte → recusa.
- `missing_facts` crítico → responder com necessidade de mais contexto (`status=needs_more_info`).
- Audit falha → voltar a `synthesize_answer` uma vez; falhar 2x → versão conservadora ou recusa.
