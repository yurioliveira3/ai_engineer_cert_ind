# Plano de Melhorias — SRAG AI Agent
> Itens diferidos do `core_plan.md` (CORE). Executar **somente após** o CORE estar entregue, ou listar como "Roadmap" no README final.

---

## Por que este arquivo existe

A análise inicial do `analytics_ql` me levou a propor um plano técnico ambicioso com muito mais escopo do que o desafio exige. O `core_plan.md` foi refatorado para conter apenas o **CORE** — o mínimo necessário para entregar o desafio e pontuar bem nos 5 critérios de avaliação (Arquitetura, Governança, Guardrails, Dados Sensíveis, Clean Code).

Este arquivo contém todo o conteúdo **diferido**, organizado por tema, para:
1. Servir como roadmap pós-PoC
2. Documentar decisões técnicas que foram consideradas e adiadas (não esquecidas)
3. Alimentar a seção "Melhorias futuras" do README final
4. Ser executado em ordem de prioridade se sobrar tempo antes da entrega

---

## Critério para diferir um item

Um item foi diferido se atende a **pelo menos um** dos critérios:
- Não é exigido pelas instruções do desafio
- Adiciona complexidade desproporcional ao valor para PoC
- Pode ser bem documentado como "evolução futura" no README sem implementação
- Tem alternativa mais simples que atende ao mesmo critério de avaliação

---

##1 — Download automatizado do DATASUS

**Por que ficou fora:** o portal do DATASUS muda layout periodicamente; discovery via HTML é frágil; para PoC, download manual com instruções claras no README atende perfeitamente.

**Plano de implementação:**

- [ ] Criar `scripts/download_srag_data.py`:
  - [ ] Receber URL ou usar `settings.datasus_csv_url` como default
  - [ ] Fazer `requests.get()` na URL do dataset
  - [ ] Parsear HTML (BeautifulSoup) para extrair links `.csv` / `.csv.gz`
  - [ ] Listar arquivos por ano (`INFLUD19.csv`, …, `INFLUD26.csv`)
  - [ ] Validar URLs com `HEAD` request
  - [ ] Download com `tqdm` (progress bar) em streaming
  - [ ] SHA256 + idempotência (skip se arquivo já existe e checksum bate)
- [ ] `src/data/download.py`:
  - [ ] `discover_srag_files(base_url) -> list[dict]`
  - [ ] `download_file(url, dest) -> Path`
  - [ ] `verify_file(path, expected_size) -> bool`
- [ ] Fallback manual documentado no README
- [ ] User-Agent customizado para evitar bloqueio de bots
- [ ] Suporte transparente a ZIP/GZ

**Dependências adicionais:**
```
requests
beautifulsoup4
tqdm
```

---

##2 — Fallback automático entre providers + validação de providers adicionais

**Por que ficou fora do CORE:** O CORE já tem adapter provider-agnostic com `LLM_PROVIDER` dispatch. Mas **não** tem fallback automático — se o provider configurado falhar, o `safe_invoke` faz retry no mesmo provider. Fallback automático entre providers é complexidade de produção, não de PoC.

**O que o CORE já tem (v3.2):**
- `src/llm/providers.py` com dicionário de 4 providers (gemini, openrouter, groq, ollama)
- `src/llm/adapter.py` com dispatch por `LLM_PROVIDER` no `.env`
- `safe_invoke` com retry/backoff que captura rate limit de qualquer provider
- `.env.example` com `LLM_PROVIDER=gemini` e `LLM_BASE_URL` para OpenAI-compatible

**Plano de implementação (extensões além do CORE):**

- [ ] **Fallback automático entre providers** (prioridade principal deste):
  - [ ] Em `src/llm/adapter.py`, adicionar lógica de fallback:
    - [ ] Se `safe_invoke` esgota retries no provider primário → tentar próximo provider da lista
    - [ ] Configurar ordem de fallback no `.env`: `LLM_FALLBACK_PROVIDERS=openrouter,groq`
    - [ ] Logar cada tentativa de fallback em `audit.llm_calls`
    - [ ] Retornar ao provider primário na próxima execução (não persistir fallback)
  - [ ] Adicionar campo `llm_provider_used` em `audit.agent_sessions` (pode diferir do configurado se houve fallback)
- [ ] **Validar tool calling em cada provider** (validação prática):
  - [ ] Testar `bind_tools()` com `LLM_PROVIDER=openrouter` e modelo free
  - [ ] Testar `bind_tools()` com `LLM_PROVIDER=groq`
  - [ ] Testar `bind_tools()` com `LLM_PROVIDER=ollama` (local)
  - [ ] Documentar em `docs/llm_test_results.md` qual provider foi testado e resultados
- [ ] **Validação extra de campos obrigatórios no adapter**:
  - [ ] Se `LLM_PROVIDER=openrouter`: exigir `LLM_BASE_URL` e `LLM_API_KEY`
  - [ ] Se `LLM_PROVIDER=ollama`: não exigir `LLM_API_KEY`
  - [ ] Mensagem de erro clara se campos obrigatórios estão faltando

**Por que vale a evolução:** sem fallback automático, se o Gemini free tier cair, o agente para. Com fallback, o agente continua funcionando com outro provider.

---

##3 — EXPLAIN-based cost gate (Camada 3 de guardrails SQL)

**Por que ficou fora:** queries do CORE são templates fixos e parametrizados; o LLM não gera SQL livre. Cost gate é útil quando há geração dinâmica de SQL.

**Plano de implementação** (adaptar `App/utils/sql_operations.py` do `analytics_ql`):

- [ ] Função `get_explain_plan(sql: str, engine) -> tuple[dict | None, str | None]`:
  - [ ] Executar `EXPLAIN (FORMAT JSON) <query>` dentro de transação com rollback
  - [ ] Capturar erros de sintaxe e tabelas/colunas inexistentes
- [ ] Função `check_plan_limits(total_cost, plan_rows) -> tuple[bool, str]`:
  - [ ] Limites sugeridos para SRAG (~165K linhas): `total_cost > 500_000` ou `plan_rows > 100_000`
- [ ] Integrar como wrapper antes de toda execução SQL
- [ ] Gravar `plan_total_cost` e `plan_rows` em `audit.query_history`

**Quando faz sentido habilitar:**
- Quando o agente passar a gerar SQL livre (opção B do core_plan.md2.2)
- Quando a base crescer (>1M linhas)

---

##4 — Integridade da query por hash SHA-256 (Camada 2)

**Por que ficou fora:** queries do CORE são templates parametrizados com SQLAlchemy, então não há janela para tampering entre geração e execução. Hash integrity faz sentido quando há armazenamento intermediário (chat history, queue, etc.).

**Plano de implementação** (adaptar `App/utils/query_protection.py`):

- [ ] `normalize_query(query: str) -> str`:
  - [ ] Remover comentários `--` e `/* */`
  - [ ] Padronizar whitespace
  - [ ] Lowercase
- [ ] `generate_query_hash(query: str) -> str`:
  - [ ] SHA-256 da query normalizada (hex)
- [ ] `validate_query_integrity(stored, execution) -> tuple[bool, str]`:
  - [ ] Comparar hashes; logar warning se diferentes
- [ ] Gravar hash em `audit.query_history.query_hash`
- [ ] Comparar antes de cada execução

**Quando faz sentido habilitar:**
- Se introduzir cache de queries no Redis ou fila assíncrona
- Se o agente persistir queries geradas para revisão humana antes de executar

---

##5 — Padrões avançados de SQL injection (Camada 1 estendida)

**Por que ficou fora:** o CORE já bloqueia DDL/DML por keywords e usa parâmetros nomeados via SQLAlchemy. Padrões avançados são paranoia útil em endpoints públicos.

**Plano de implementação** (adaptar `validate_query_safety_enhanced`):

- [ ] Detecção de padrões além do keyword blocking:
  - [ ] `;.*--` (statement terminator + comentário)
  - [ ] `union\s+select` (UNION attacks)
  - [ ] `or\s+1\s*=\s*1` / `and\s+1\s*=\s*1`
  - [ ] `\'.*or.*\'.*=.*\'` (quote-based injection)
  - [ ] Multi-statement (mais de um `;` na query)
- [ ] Retornar `(is_safe, reason, metadata)` com `checks_performed` para auditoria
- [ ] Testes: `test_union_select_blocked`, `test_or_1_eq_1_blocked`, `test_multiple_statements_blocked`

**Quando faz sentido habilitar:**
- Quando expor o agente em endpoint web público
- Quando o input do usuário chegar concatenado em SQL (mesmo via toolkit do LangChain)

---

##6 — RAG enhanced: TTL + edge condicional

**CORE tem:** indexar notícias buscadas + busca semântica simples no pgvector.

**Por que ficou fora:** TTL e edge condicional otimizam custo, mas a PoC pode rodar a busca web a cada execução (~5 buscas, free tier do DuckDuckGo).

**Plano de implementação:**

- [ ] Campo `news_cache_ttl_days` em `Settings` (default 7)
- [ ] Tabela `news.news_embeddings` ganha índice em `indexed_at`
- [ ] `NewsEmbeddingsRepository.similarity_search(query, k=5, max_age_days=7)`:
  - [ ] Filtro `WHERE indexed_at >= NOW() - INTERVAL ':n days'`
  - [ ] Threshold de relevância (`score >= 0.6`)
- [ ] `NewsEmbeddingsRepository.purge_old(days=30)`:
  - [ ] Job manual ou cron para conter crescimento
- [ ] **No orquestrador (LangGraph):**
  - [ ] Separar nós `retrieve_news_rag` e `search_news_fresh`
  - [ ] Edge condicional: se `len(news_from_rag) >= 3` pula para `analyze`, senão passa por `search_news_fresh` + `index_fresh_news`
  - [ ] Dedupe por URL ao consolidar `news_from_rag + news_fresh`
- [ ] Testes: `test_similarity_search_respects_ttl`, `test_purge_old_removes_stale`

**Quando faz sentido habilitar:**
- Quando uso passar de tier free e cada busca custar dinheiro
- Quando latência da busca web virar gargalo
- Quando quiser garantir reprodutibilidade (cache stable entre runs)

---

##7 — First-layer router (saudações / perguntas vagas)

**Por que ficou fora:** o CORE não tem input livre na UI — usuário só clica em "Gerar Relatório". Router faz sentido quando há chat aberto.

**Plano de implementação** (adaptar `App/utils/first_layer.py`):

- [ ] Adicionar `st.text_input("Pergunta livre (opcional)")` na UI
- [ ] Funções:
  - [ ] `is_greeting_or_small_talk(text) -> bool` com regex de saudações em PT-BR
  - [ ] `is_vague_question(text) -> bool` com padrões de vagueza
- [ ] Antes de invocar agente:
  - [ ] Se saudação: responde com mensagem padrão + sugestões pré-definidas (sem LLM)
  - [ ] Se vaga: responde pedindo especificidade (sem LLM)
  - [ ] Caso contrário: invoca o agente normalmente
- [ ] Logar decisão em `audit.agent_decisions` com `step_name = "first_layer_router"`

**Quando faz sentido habilitar:**
- Quando UI evoluir para chat conversacional
- Quando custo de LLM começar a importar

---

##8 — Trendline OLS no gráfico mensal

**Por que ficou fora:** análise textual gerada pelo LLM já vai cobrir a tendência. Trendline é polish visual.

**Plano de implementação** (adaptar `add_trendline_if_applicable` do `chart_generator.py`):

- [ ] No `chart_tool.generate_monthly_cases_chart`:
  - [ ] Regressão OLS simples com `np.polyfit` em (mês_idx, casos)
  - [ ] Calcular R² = 1 - SS_res / SS_tot
  - [ ] Adicionar trendline **apenas se R² >= 0.20** (`R2_THRESHOLD`)
  - [ ] Linha vermelha tracejada, hover com equação e R²
  - [ ] Retornar `regression_info = {slope, intercept, r_squared, equation}`
- [ ] Injetar `regression_info` no payload do nó `analyze`:
  - [ ] LLM passa a poder citar "a tendência de crescimento mensal é de X casos/mês com correlação R²=Y"
- [ ] Testes: `test_trendline_added_when_r2_high`, `test_trendline_skipped_when_r2_low`

**Quando faz sentido habilitar:**
- Quando quiser elevar o valor analítico do relatório
- Como diferencial visual em apresentação

---

##9 — Schema de auditoria — extensões além do CORE

**CORE tem:** schema `audit.*` com 4 tabelas (`agent_sessions`, `agent_decisions`, `query_history`, `llm_calls`) + replicação em arquivo JSON.

**Extensões diferidas:**

- [ ] Tabela `audit.metric_calculations` para cada métrica calculada (histórico de evolução):
  ```sql
  CREATE TABLE audit.metric_calculations (
      id          BIGSERIAL PRIMARY KEY,
      session_id  UUID REFERENCES audit.agent_sessions(id),
      metric_name VARCHAR(50),
      value       DECIMAL(10,4),
      period_start DATE,
      period_end   DATE,
      uf          VARCHAR(2) NULL,
      out_of_range BOOLEAN DEFAULT FALSE,
      computed_at TIMESTAMPTZ DEFAULT NOW()
  );
  ```
- [ ] Dashboard de auditoria separado (Grafana/Metabase apontando para `audit.*`)
- [ ] Retenção configurável: job para arquivar sessões > 90 dias
- [ ] Exportação de audit log para SIEM (formato CEF/LEEF)

---

##10 — Cobertura ampla de testes (>15 testes por módulo)

**CORE tem:** smoke tests + happy path em cada módulo (~5-7 testes por módulo).

**Extensões diferidas:**

- [ ] `tests/test_etl.py`: testes de edge cases (CSV vazio, encoding misto, colunas faltantes)
- [ ] `tests/test_metrics.py`: testes de boundary (período sem dados, UF inválida, ano fora do range)
- [ ] `tests/test_agent.py`: testes de degradação (cada tool falha individualmente)
- [ ] `tests/test_guardrails.py`: 9 testes adicionais (hash integrity, EXPLAIN gate, injection patterns)
- [ ] `tests/test_embeddings.py`: testes de TTL e purge
- [ ] `tests/test_orchestrator.py`: testes de edge condicional (cache hit vs miss)
- [ ] Coverage report com `pytest-cov` (alvo: 80%+)
- [ ] CI/CD via GitHub Actions

---

##11 — Validação cruzada automatizada com fontes oficiais

**CORE tem:** validação manual documentada em `docs/metrics_validation.md`.

**Extensões diferidas:**

- [ ] Script `scripts/validate_against_external.py`:
  - [ ] Scraping leve do painel SRAG do Ministério (`gov.br/saude/.../srag`)
  - [ ] Scraping leve do InfoGripe (`info.gripe.fiocruz.br`)
  - [ ] Comparação automática de taxa de mortalidade e UTI
  - [ ] Alerta se diferença > 10%
- [ ] Rodar semanalmente como cron

---

##12 — Multi-agent orchestration (futuro)

**Por que ficou fora:** LangGraph single-agent atende plenamente uma PoC. Multi-agent é interessante mas adiciona complexidade que não pontua em nenhum critério de avaliação.

**Plano de implementação:**

- [ ] Refatorar para CrewAI ou LangGraph multi-agent:
  - [ ] Agente "Analista de Dados": foca em métricas e queries
  - [ ] Agente "Pesquisador": foca em busca de notícias e contexto
  - [ ] Agente "Editor": consolida e formata o relatório
- [ ] Supervisor agent decide ordem de execução
- [ ] Cada agente tem prompt e tools próprios

---

##13 — Cache de LLM para desenvolvimento

**Por que ficou fora:** Gemini free tier comporta bem o uso da PoC.

**Plano de implementação:**

- [ ] Cache simples em `dict` durante desenvolvimento:
  - [ ] Chave: hash do prompt rendered
  - [ ] Valor: resposta do LLM
  - [ ] Persistência opcional em SQLite local
- [ ] Habilitado apenas se `settings.llm_cache_enabled == True`
- [ ] Útil para rodar testes E2E sem consumir quota

---

##14 — Multi-disease support (futuro)

**Por que ficou fora:** desafio é específico para SRAG.

**Plano de implementação:**

- [ ] Generalizar `srag_cases` → `disease_cases` com discriminador
- [ ] Templates de queries parametrizados por doença
- [ ] Configuração de fontes de notícias por doença
- [ ] Multi-tabbed UI no Streamlit

---

##15 — Deploy em cloud

**Por que ficou fora:** repositório com `docker-compose up` é suficiente para a entrega.

**Plano de implementação:**

- [ ] Dockerfile multi-stage para imagem otimizada
- [ ] Deploy em Cloud Run (Google) ou ECS (AWS)
- [ ] Postgres gerenciado (Cloud SQL / RDS)
- [ ] Streamlit por trás de IAP / Cognito
- [ ] CI/CD pipeline com GitHub Actions

---

## Resumo — Ordem de prioridade se sobrar tempo

Se o CORE terminar com folga e houver tempo extra antes da entrega, sugiro implementar nesta ordem (maior valor por hora investida):

| Ordem | Item | Esforço | Valor para avaliação |
|------:|------|--------:|---------------------|
| 1 |1 Download automatizado | 0.5 dia | Médio (Clean Code) |
| 2 |8 Trendline OLS | 0.5 dia | Alto (valor analítico visível) |
| 3 |6 RAG TTL + edge condicional | 1 dia | Alto (Arquitetura) |
| 4 |3 EXPLAIN cost gate | 0.5 dia | Alto (Guardrails) |
| 5 |5 Padrões avançados de injection | 0.5 dia | Médio (Guardrails) |
| 6 |4 Hash integrity | 0.5 dia | Médio (Governança) |
| 7 |7 First-layer router | 1 dia | Baixo (UX) |
| 8 |2 Fallback automático entre providers | 1 dia | Médio (resiliência) |
| 9 |10 Testes ampliados | 2 dias | Médio (Clean Code) |
| 10 |11 Validação cruzada automatizada | 1 dia | Médio (Governança) |

**Itens 1, 2, 3, 4 são os de maior ROI** — se sobrarem 2-3 dias, focar neles.

---

## Como usar este arquivo

1. **Durante desenvolvimento do CORE:** não consultar. Manter foco.
2. **Após CORE entregue:** se houver folga, atacar na ordem de prioridade acima.
3. **Na escrita do README final:** copiar a seção "Resumo" como "Melhorias Futuras" no README do `srag-agent`. Cita maturidade técnica sem precisar implementar.
4. **Como histórico de decisão:** registra **por que** cada item foi avaliado e adiado — útil em revisão técnica ou apresentação ao avaliador.
