# Ideias — AI Agent PoC

## Problema
- Consultar dados do Open DATASUS (~165K linhas) + notícias em tempo real
- Gerar relatórios automatizados usando IA Generativa + RAG

## Métricas do relatório
- Taxa de aumento de casos, mortalidade, ocupação UTI, vacinação
- Gráficos: casos diários (30 dias) + casos mensais (12 meses)

## Arquitetura (definida)
- **Orquestrador**: LangGraph (fluxo sequencial)
- **LLM**: Gemini via `langchain-google-genai`
- **4 Tools**: SQL (templates parametrizados), News (DuckDuckGo), Chart (Plotly), Report (Markdown + PDF)
- **RAG**: Notícias indexadas no pgvector (model BAAI/bge-large-en-v1.5)
- **Auditoria**: schema `audit.*` no Postgres + replicação JSON
- **Guardrails SQL**: DDL/DML blocking, timeout, LIMIT, validação de queries

## Stack
Python, LangChain, LangGraph, Gemini, PostgreSQL + pgvector, Streamlit, Docker

## Clean Code & Dados Sensíveis
- Prompts versionados em `.txt`, config via pydantic-settings, logging estruturado
- Remoção de PII, agregação por faixa etária, validação de range das métricas

## Critérios de avaliação
Arquitetura | Governança/Transparência | Guardrails | Dados Sensíveis | Clean Code

## Fases (~18-25 dias)
0. Setup (Docker, dependências, LLM validation)
1. ETL (download, limpeza, carga no Postgres)
2. Core Agent (4 tools + orquestrador)
3. Métricas e Validação
4. UI Streamlit
5. Documentação e Polish

## Referência
- Projeto Analyticsql (https://github.com/yurioliveira3/analytics_ql)
- Revisar arquitetura e o que pode ser reaprovietado para a POC

## Entrega
Repositório público no GitHub + README + diagrama de arquitetura em PDF
