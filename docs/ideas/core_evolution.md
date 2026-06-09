# Core Evolution — SRAG AI Agent
> **Pré-requisito:** `core_foundations.md` entregue (todos os testes green, banco populado, LLM respondendo).
> **Entregável:** agente LangGraph completo com 4 tools, UI Streamlit, relatório PDF, testes cobrindo fluxo completo.
> **Sequência:** `core_foundations.md` → este arquivo → `improvements_plan.md`

---

## Fase 2 — Core Agent (continuação)

### 2.3 — News Search Tool (com indexação pgvector)

#### 2.3.T — Testes primeiro (`tests/test_news_tool.py`)

- [x] `test_search_and_index_returns_results` — retorna lista não-vazia com título, url, snippet
- [x] `test_search_indexes_news_in_pgvector` — após `search_and_index_news`, `COUNT(*)` em `news.news_embeddings` cresce
- [x] `test_search_upsert_is_idempotent` — rodar 2 vezes com mesma query não duplica URLs
- [x] `test_semantic_search_returns_topk` — `semantic_search_news` retorna até k resultados
- [x] `test_search_rate_limit_respected` — mais de 5 resultados por busca levanta exceção

---

- [x] `src/agent/tools/news_tool.py`:
  - `search_and_index_news(query: str) -> list[dict]`:
    1. `DuckDuckGoSearchResults(max_results=5, region="br-pt", time="m")`
    2. Para cada resultado: gerar embedding de `title + snippet`, chamar `repo.upsert()`
    3. Retornar lista `{title, url, snippet, source, published_at}` (published_at=None para DDG)
  - `semantic_search_news(query: str, k=3) -> list[dict]` — chama `repo.similarity_search(query, k)`
- [x] Domínios confiáveis (marcar resultados de fora como "fonte não-verificada"):
  `gov.br`, `fiocruz.br`, `who.int`, `saude.gov.br`, `paho.org`, `g1.globo.com`, `folha.uol.com.br`
- [x] Rate limiting: máximo 5 resultados por busca (max_results > 5 rejeita)
- [ ] ~~Fallback Tavily~~ → adiado para improvements (só DuckDuckGo por ora)

---

### 2.4 — Chart Tool

#### 2.4.T — Testes primeiro (`tests/test_chart_tool.py`)

- [x] `test_generate_daily_chart_returns_path` — retorna path de PNG existente
- [x] `test_generate_monthly_chart_returns_path`
- [x] `test_chart_with_empty_data_does_not_crash` — dados vazios geram gráfico com nota "sem dados"
- [x] `test_png_export_has_content` — arquivo PNG > 1KB

---

- [x] `src/agent/tools/chart_tool.py`:
  - `generate_daily_cases_chart(data: list[dict]) -> tuple[str, Figure]` — line chart, eixo X datas (dd/mm), salva `data/charts/daily_cases.png`
  - `generate_monthly_cases_chart(data: list[dict]) -> tuple[str, Figure]` — bar chart, eixo X meses (mmm/yyyy), salva `data/charts/monthly_cases.png`
- [x] Configuração visual: template `plotly_white`, labels em português, annotation com data de referência dos dados
- [x] Export PNG: `fig.write_image(path, width=800, height=400)` via `kaleido`
- [ ] ~~kaleido fallback matplotlib~~ → adiada (kaleido funciona no Docker)

**Armadilha:** `kaleido` pode precisar de dependências extras no Docker — testar cedo. Fallback: `matplotlib` para export estático.

---

### 2.5 — Report Tool

#### 2.5.T — Testes primeiro (`tests/test_report_tool.py`)

- [x] `test_generate_report_returns_markdown` — markdown contém as 4 métricas
- [x] `test_generate_report_returns_pdf_path` — PDF criado em `data/reports/`
- [x] `test_pdf_opens_without_error` — arquivo PDF é válido (header `%PDF`)
- [x] `test_report_contains_news_section` — seção de notícias presente quando `news` não-vazia
- [x] `test_portuguese_accents_in_pdf` — verificar caracteres acentuados (ç, ã, é) não corrompidos

---

- [x] `src/agent/tools/report_tool.py`:
  - `generate_report(metrics: dict, charts: dict, news: list, analysis: str) -> dict` → `{"markdown": str, "pdf_path": str}`
  - Template markdown:
    ```markdown
    # Relatório SRAG — {data_geracao}
    ## Resumo executivo
    {analysis}
    ## Métricas
    | Métrica | Valor | Período |
    |---------|-------|---------|
    | Taxa de aumento de casos | {X}% | ... |
    | Taxa de mortalidade | {Y}% | ... |
    | Taxa de ocupação de UTI | {Z}% | ... |
    | Taxa de vacinação | {W}% | ... |
    ## Casos diários — Últimos 30 dias
    ## Casos mensais — Últimos 12 meses
    ## Contexto — Notícias recentes
    ## Fontes
    ---
    *Relatório gerado automaticamente por SRAG Agent em {data_hora}*
    ```
  - PDF com `fpdf2`: página A4, fonte DejaVu (Helvetica fallback), rodapé com numeração "Página X de Y"

**Armadilha:** `fpdf2` com UTF-8 PT-BR pode precisar de `add_font()` para TTF Unicode. Fallback: `weasyprint`.

---

### 2.8 — Guardrails runtime & Logging

> **Implementar antes do Orquestrador (2.7).** O `AgentAuditLogger` e o decorator `@audit_step` são usados em todos os nodes do LangGraph. Implementar aqui, integrar em 2.7.

#### 2.8.T — Testes primeiro (`tests/test_guardrails.py` — complementar aos do Foundations)

- [x] `test_audit_logger_start_session` — `start_session()` cria linha em `audit.agent_sessions`, retorna UUID
- [x] `test_audit_logger_end_session` — `end_session()` atualiza `finished_at` e `status`
- [x] `test_audit_logger_log_decision` — `log_decision()` cria linha em `audit.agent_decisions` com `session_id` correto
- [x] `test_audit_logger_log_query_updates_session_id` — `log_query()` preenche `session_id` na linha de `audit.query_history`
- [x] `test_json_log_file_created` — arquivo `data/logs/session_{id}.json` criado após `end_session()`
- [x] `test_sql_injection_blocked` — input `"; DROP TABLE srag.srag_cases; --` bloqueado
- [x] `test_prompt_injection_blocked` — "ignore suas instruções anteriores" detectado e sanitizado
- [x] `test_output_pii_filter` — padrão de CPF no output mascarado como `XXX.XXX.XXX-XX`
- [x] `test_metric_range_warning` — mortalidade > 50% gera warning no relatório

---

- [x] `src/agent/logging_config.py`:
  - `setup_logger(name, level)` — rotação diária: `logs/srag_agent_YYYYMMDD.log` + console INFO+
  - `get_logger(name=None)`
  - `AgentAuditLogger`:
    ```python
    class AgentAuditLogger:
        def start_session(self, llm_provider, llm_model) -> uuid: ...
        def log_decision(self, step, tool, input_summary, output_summary, duration_ms, success): ...
        def log_query(self, query_text, query_hash, exec_ms, blocked=False, reason=None): ...
        def log_llm_call(self, prompt_name, prompt_file, prompt_hash, response_summary, tokens_in, tokens_out, duration_ms): ...
        def end_session(self, status, error=None): ...
        def get_session_log(self, session_id) -> dict: ...
    ```
  - Cada INSERT no Postgres é replicado em `data/logs/session_{session_id}.json` (backup offline)
  - Decorator `@audit_step(step_name)` disponível mas nodes usam `log_decision()` direto (SPEC_DEVIATION documentado)

- [x] `src/agent/guardrails.py` — adicionar ao que já existe do Foundations:
  - `validate_user_input(text: str) -> str` — limite 1000 chars, sanitizar especiais, detectar "ignore as instruções anteriores" e SQL embutido
  - `validate_metrics(metrics: dict) -> dict` — ranges: mortalidade 0-100% (flag > 50%), UTI 0-100%, vacinação 0-100%, aumento -100% a +1000% (flag > 500%)
  - `validate_output_pii(text: str) -> str` — regex para CPF, telefone, email; mascarar e logar warning

**Commit:** `test+feat: audit logger, guardrails runtime — AgentAuditLogger, @audit_step, PII filter` ✅

---

### 2.7 — Orquestrador LangGraph

> **Pré-requisito:** Fase 2.8 (Logger) implementada. O orquestrador usa `@audit_step` e `AgentAuditLogger` em todos os nodes.

#### 2.7.T — Testes primeiro (`tests/test_orchestrator.py`)

- [x] `test_agent_full_flow` — fluxo completo executa sem erro, state final tem todas as chaves
- [x] `test_agent_returns_all_metrics` — `state["metrics"]` contém as 4 métricas
- [x] `test_agent_generates_charts` — `state["charts"]` contém paths de 2 gráficos existentes (implícito em full_flow)
- [x] `test_agent_generates_report` — `state["report_markdown"]` não-vazio, `state["report_pdf_path"]` aponta para arquivo (implícito em full_flow)
- [x] `test_agent_graceful_degradation_news` — se news tool levantar exceção, agente continua e relatório é gerado sem seção de notícias
- [x] `test_agent_graceful_degradation_metrics` — se uma métrica falhar, as outras 3 continuam
- [x] `test_audit_session_created` — `audit.agent_sessions` recebe linha ao invocar o agente
- [x] `test_audit_decisions_logged` — `audit.agent_decisions` tem 6 linhas (uma por node) após execução completa

---

- [x] `src/agent/orchestrator.py`:

  **State:**
  ```python
  class AgentState(TypedDict):
      messages:        Annotated[list, add_messages]
      metrics:         dict
      charts:          dict
      news:            list
      news_semantic:   list
      analysis:        str
      report_markdown: str
      report_pdf_path: str
      error:           str | None
      session_id:      str
  ```

  **Nodes (fluxo sequencial) — cada um chama `audit_logger.log_decision()` direto (SPEC_DEVIATION):**
  - `calculate_metrics` — chama SQL tool para cada uma das 4 métricas; erros individuais não param o fluxo
  - `generate_charts` — chama SQL tool para dados temporais + Chart tool
  - `search_news` — `search_and_index_news(query)` com query derivada das métricas calculadas
  - `retrieve_semantic` — `semantic_search_news(query, k=3)` no índice (passo de RAG demonstrável)
  - `analyze` — monta payload JSON `{metrics, period, news_consolidated, news_sources, data_freshness}`, chama LLM via `safe_invoke` com `render_prompt("analyze_metrics", payload=...)`
  - `compile_report` — chama Report tool com todos os dados do state

  **Grafo:**
  ```
  START → calculate_metrics → generate_charts → search_news
        → retrieve_semantic → analyze → compile_report → END
  ```

  > Edge condicional cache-hit foi diferido — `improvements_plan.md`§6. CORE roda busca + index a cada execução.

- [x] O payload do nó `analyze` deve incluir `data_ref` (última data do DATASUS) e `data_hora_consulta` (timestamp da execução), para que os prompts possam deixar explícita a distinção entre:
  - **Dados históricos:** métricas derivadas do DATASUS, cuja cobertura vai até `data_ref`
  - **Notícias em tempo real:** consultadas no momento da execução (`data_hora_consulta`)

- [x] `scripts/run_agent.py` para testar via CLI:
  ```python
  agent = create_agent(Settings())
  result = agent.invoke({"messages": [("user", "Gere o relatório SRAG")]})
  print(result["report_markdown"])
  ```

**Commit:** `test+feat: LangGraph orchestrator with sequential flow and audit integration` ✅

---

## Fase 3 — Métricas & Validação

### 3.1 — Queries finais das métricas

> **Diferença em relação à Fase 2.2 do Foundations:** Em 2.2 foram definidos os templates (nomes das queries e parametrização). Aqui o SQL completo é escrito e validado contra dados reais. O arquivo `src/data/queries.py` que existe como esboço em 2.2 é finalizado aqui.

#### 3.1.T — Testes (`tests/test_metrics.py`)

- [x] `test_mortality_rate_in_range` — 0 < resultado < 50
- [x] `test_icu_rate_in_range` — 0 < resultado < 80
- [x] `test_vaccination_rate_in_range` — 0 < resultado < 100 (para anos >= 2021)
- [x] `test_case_increase_rate_not_null` — retorna resultado (None aceitável quando semana anterior = 0)
- [x] `test_daily_cases_30d_has_data` — retorna >= 1 linha
- [x] `test_monthly_cases_12m_has_data`
- [x] `test_metrics_with_max_dt_notific_as_ref` — usando `MAX(dt_notific)` como referência, não `NOW()`

---

Queries finais em `src/data/queries.py` (usar `MAX(dt_notific)` como `:data_ref` default): ✅

- **Taxa de aumento de casos:** ✅ (colunas renomeadas para `casos_semana_atual`, `casos_semana_anterior`, `taxa_aumento`; NULLIF para divisão por zero)

- **Taxa de mortalidade:** ✅ (7.47% validado contra dados reais)

- **Taxa de UTI:** ✅ (27.45% validado; documentado como proporção de internados que foram para UTI, não ocupação de leitos)

- **Taxa de vacinação:** ✅ (53.44% validado para anos >= 2021)

---

### 3.2 — Validação cruzada manual

- [ ] Acessar painel SRAG do Ministério: https://www.gov.br/saude/pt-br/composicao/svsa/cnie/srag
- [ ] Acessar InfoGripe da Fiocruz: http://info.gripe.fiocruz.br/
- [x] Para cada métrica: anotar valor da fonte oficial, comparar com o nosso, documentar em `docs/metrics_validation.md`
- [ ] Margem aceitável: ±5%. Se > 10%: investigar filtro de `CLASSI_FIN` ou período de referência

**Commit:** `feat: metrics queries validated and tested` ✅

---

## Fase 4 — UI Streamlit

### 4.T — Testes (`tests/test_ui.py` — smoke tests)

- [x] `test_app_imports_without_error` — `import src.ui.app` não levanta exceção
- [x] `test_session_state_persists_report` — após mock de `create_agent`, `st.session_state["report"]` é populado

---

### 4.1 — Layout da página

- [x] `src/ui/app.py`:
  ```python
  st.set_page_config(page_title="SRAG Agent", page_icon="🦠", layout="wide")
  ```
  - Sidebar: selectbox provider LLM, selectbox modelo, selectbox UF (Todos + estados), date input data de referência, botão "Gerar Relatório"
  - Área principal: header com título, placeholder para relatório

- [x] Estados da UI:
  - Inicial: "Clique em **Gerar Relatório** para começar"
  - Gerando: `st.spinner("Gerando relatório... Isso pode levar até 1 minuto")`
  - Pronto: relatório, gráficos, botão download
  - Erro: `st.error()` com mensagem clara

---

### 4.2 — Integração com o agente

- [x] Handler do botão:
  ```python
  if st.sidebar.button("Gerar Relatório"):
      with st.spinner("Gerando relatório..."):
          agent = create_agent(settings)
          result = agent.invoke({"messages": [("user", "Gere o relatório SRAG")]})
          st.session_state["report"] = result
  ```
- [x] 4 métricas em destaque com `st.metric()` em 4 colunas

---

### 4.3 — Gráficos, relatório e download

- [x] `st.image(daily_path)` + `st.image(monthly_path)` para gráficos PNG
- [x] `st.markdown(report_markdown)` para o corpo do relatório
- [x] Botão de download PDF:
  ```python
  with open(pdf_path, "rb") as f:
      st.download_button(
          label="Baixar relatório em PDF",
          data=f,
          file_name=f"relatorio_srag_{timestamp}.pdf",
          mime="application/pdf"
      )
  ```

---

### 4.4 — Expander de auditoria

- [x] ```python
  with st.expander("🔍 Auditoria — Decisões do agente"):
      for entry in session_logs:
          st.json(entry)
  ```
- [x] Mostrar: análise LLM, notícias recuperadas, configuração utilizada
- [x] Seção de fontes: URLs consultadas, fonte verificada vs não-verificada

**Commit:** `feat: streamlit UI with report, download and audit expander` ✅

---

## Fase 5 — Documentação & Polish

### 5.1 — README profissional

Seções obrigatórias:
- [ ] Visão geral + screenshot da interface
- [ ] Arquitetura (link para `docs/architecture.pdf`)
- [ ] Stack tecnológica (tabela: ferramenta / versão / propósito / justificativa)
- [ ] Como executar (passo a passo: clone → `.env` → download CSV → `docker compose up --build` → `seed_db.py` → `localhost:8501`)
- [ ] **Temporalidade dos dados** *(seção obrigatória para o avaliador)*:
  - Notícias: consultadas em **tempo real** a cada execução do agente (DuckDuckGo/Tavily)
  - Métricas e gráficos: derivados dos dados históricos do DATASUS — a cobertura vai até a última data disponível no dataset baixado (documentar qual é essa data). O agente usa `MAX(dt_notific)` como referência, não `NOW()`.
  - Essa distinção é exibida no próprio relatório gerado e nos prompts do LLM.
- [ ] Métricas (fórmula + query + premissas, incluindo distinção taxa UTI vs ocupação de leitos)
- [ ] Tratamento de dados sensíveis (LGPD, PII removido, agregação de outputs)
- [ ] Guardrails (input, output, SQL, logging)
- [ ] Testes (`pytest tests/ -v`)
- [ ] Melhorias futuras (copiar tabela de prioridades de `improvements_plan.md` — demonstra maturidade técnica sem precisar implementar)

---

### 5.2 — Diagrama de arquitetura

- [ ] `docs/architecture.drawio` com componentes obrigatórios:
  - Agente Principal (Orquestrador), 4 Tools, LLM Provider (anotado "provider-agnostic"), PostgreSQL + pgvector, Streamlit UI, camada de Guardrails & Logging (contorno pontilhado), fontes de notícias, container Docker envolvendo tudo
- [ ] Exportar para `docs/architecture.pdf`

---

### 5.3 — Code cleanup

- [x] Docstrings Google style em todas as funções públicas e módulos
- [x] Type hints em todos os parâmetros e retornos (existing code already had them)
- [x] `ruff check . --fix` + `ruff format .` — all checks pass
- [x] Remover prints de debug, funções não usadas, imports desnecessários

---

### 5.4 — Revisão final vs critérios

| Critério | Como o agente atende |
|----------|----------------------|
| **Arquitetura** | LangGraph single-agent + 4 Tools + RAG via pgvector + adapter provider-agnostic. Diagrama PDF. |
| **Governança e Transparência** | Schema `audit.*` (4 tabelas) + replicação JSON + expander no Streamlit. Prompts versionados com hash em `audit.llm_calls`. |
| **Guardrails** | Input validation, PII filter no output, validação de range de métricas, SQL keywords + timeout + LIMIT, `safe_invoke` com backoff. |
| **Dados Sensíveis** | LGPD documentado, PII verificado e removido do CSV, outputs com agregação por faixa etária. |
| **Clean Code** | Type hints, docstrings, ruff, prompts versionados, testes TDD por componente. |

- [ ] Teste final end-to-end em máquina limpa seguindo README exatamente

**Commit:** `docs: README, architecture diagram, final review`

---

## Mapa de paralelismo por agente

Identifica o que pode ser executado simultaneamente por agentes diferentes (ou desenvolvedores diferentes) sem criar conflito ou bloqueio de dependência.

### Bloco 0 — Serial (Foundations inteiro)
Cada etapa depende da anterior. Sem paralelismo possível.
```
0.1 → 0.2 → 0.3 → [2.1 Adapter] → 0.4 → ETL (1.x) → 2.2 SQL Tool → 2.3 Embeddings → 2.4 Prompts
```

### Bloco 1 — Paralelo (após Foundations completo)
Estas 4 tarefas são completamente independentes entre si. Podem ser distribuídas para 4 agentes simultâneos:

```
┌─────────────────────────────────────────────────────────────┐
│  Foundations completo (banco populado + SQL tool + embeds)  │
└──────────────┬──────────────────────────────────────────────┘
               │
       ┌───────┼───────────────────┐
       ▼       ▼                   ▼           ▼
  [Agente A] [Agente B]      [Agente C]  [Agente D]
  2.3 News   2.4 Chart       2.5 Report  2.8 Logger
  Tool       Tool            Tool        (AgentAuditLogger)
       │       │                   │           │
       └───────┴───────────────────┴─────┬─────┘
                                         ▼
                                  2.7 Orquestrador
                                  (depende dos 4)
```

**O que cada agente paralelo precisa:**
| Agente | Depende de | Produz |
|--------|-----------|--------|
| A — News Tool | `NewsEmbeddingsRepository` (Foundations 2.3) | `src/agent/tools/news_tool.py` |
| B — Chart Tool | SQL Tool (Foundations 2.2), Plotly/kaleido | `src/agent/tools/chart_tool.py` |
| C — Report Tool | fpdf2, template markdown | `src/agent/tools/report_tool.py` |
| D — Logger | Schema `audit.*` no banco (Foundations 0.2) | `src/agent/logging_config.py` |

### Bloco 2 — Serial (Orquestrador)
Só pode começar quando os 4 agentes do Bloco 1 terminarem.
```
2.7 Orquestrador → scripts/run_agent.py (validação E2E via CLI)
```

### Bloco 3 — Paralelo (após Orquestrador)
```
┌─────────────────────────────────────────┐
│  Orquestrador funcionando via CLI       │
└──────────────┬──────────────────────────┘
               │
       ┌───────┴───────────────────┐
       ▼                           ▼
  [Agente A]                 [Agente B]
  3.1 Queries finais         5.2 Diagrama de
  + 3.2 Validação cruzada    arquitetura (Draw.io → PDF)
  + test_metrics.py          (100% independente de código)
       │                           │
       └───────────────────────────┘
                     ▼
              4 UI Streamlit
              (depende do agente completo)
```

### Bloco 4 — Serial (UI + Docs)
```
4 UI → 5.1 README → 5.3 Cleanup → 5.4 Revisão final
```

### Resumo de ganho de tempo com paralelismo

Sem paralelismo (serial puro): estimativa de 18-22 dias.

Com Bloco 1 paralelo (4 agentes simultâneos):
- Bloco 1 passa de ~4 dias para ~1-2 dias (o mais lento dos 4 agentes)
- Economia estimada: **2-3 dias**

Com Bloco 3 paralelo:
- Diagrama (5.2) pode ser feito enquanto queries são validadas
- Economia estimada: **0.5 dia adicional**

---

## Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| LLM tool calling falha | Baixo | Baixa | Validado: `langchain-google-genai` 4.x + `gemini-2.5-flash` funciona. Fallback: trocar `LLM_PROVIDER` no `.env` |
| CSV DATASUS com encoding/formato inesperado | Médio | Alta | Testar múltiplos encodings. `errors='coerce'` em conversões |
| Métricas com valores implausíveis | Alto | Média | Validação cruzada manual (Fase 3.2) |
| DuckDuckGo retorna resultados irrelevantes | Baixo | Média | Filtro por domínios. Tavily como fallback |
| `kaleido` não funciona no Docker | Médio | Média | Testar cedo (Fase 2.4). Fallback: matplotlib |
| `fpdf2` falha com acentos PT-BR | Médio | Média | `add_font()` para TTF Unicode; fallback: `weasyprint` |
| Rate limits Gemini free tier | Médio | Média | `safe_invoke` com backoff (já no Foundations) |
| `BAAI/bge-large-en-v1.5` pesado em CPU | Baixo | Média | Volume Docker para cachear; alternativa: `bge-m3` |
| Score baixo para queries PT-BR nos embeddings | Médio | Média | Avaliar `BAAI/bge-m3` (multilingual) se necessário |
| Escopo estoura o CORE | Médio | Média | Disciplina: não puxar itens de `improvements_plan.md` até o Evolution terminar |

---

## Decisões técnicas

| Decisão | Escolha | Justificativa |
|---------|---------|---------------|
| Orquestração | LangGraph, fluxo sequencial | Atende a PoC; multi-agent em `improvements_plan.md`§12 |
| Banco de dados | PostgreSQL 16 + pgvector | SQL + embeddings no mesmo banco; reaproveitado do `analytics_ql` |
| LLM Provider | Provider-agnostic (default: `gemini-2.5-flash`) | Trocar LLM = trocar 1 variável no `.env` |
| Robustez LLM | `safe_invoke` com retry/backoff exponencial | Essencial para free tiers |
| RAG | pgvector + `BAAI/bge-large-en-v1.5` (1024-dim) | Atende pré-requisito; reaproveitado |
| Busca de notícias | DuckDuckGo (free, sem API key) | Tavily como contingência |
| Gráficos | Plotly + kaleido | Interativo no Streamlit, estático no PDF |
| PDF | `fpdf2` | Leve; fallback `weasyprint` |
| Download DATASUS | Manual com instruções no README | Automatizado em `improvements_plan.md`§1 |
| SQL Guardrails | 1 camada robusta (keywords + timeout + LIMIT) | Camadas avançadas em `improvements_plan.md`§3-5 |
| Testes | TDD por componente (pytest) | Cobertura ampla em `improvements_plan.md`§10 |
| UI | Streamlit, apenas botão "Gerar Relatório" | First-layer router em `improvements_plan.md`§7 |

---

## Sequência de commits sugerida

Padrão TDD: cada commit une o teste (vermelho) e a implementação (verde). Commits separados de test/feat só quando a escrita do teste precede a implementação por muito tempo (ex: infra de banco).

```
--- FOUNDATIONS ---
1.  chore: initial project structure
2.  feat: docker compose — postgres, pgvector, all init-scripts (audit + news schemas)
3.  test+feat: provider-agnostic LLM adapter with safe_invoke
4.  feat: LLM connectivity validation with tool calling (0.4)
5.  test+feat: ETL pipeline — column selection and PII removal
6.  feat: ETL pipeline — postgres load and data validation
7.  test+feat: SQL tool with guardrails (keywords, timeout, LIMIT, audit insert)
8.  test+feat: embeddings service and NewsEmbeddingsRepository
9.  feat: versioned prompts with load/render and hash

--- EVOLUTION ---
10. test+feat: news search tool with pgvector indexing and DuckDuckGo
11. test+feat: chart generation tool (daily 30d + monthly 12m)
12. test+feat: report generation tool (markdown + PDF)
13. test+feat: audit logger — AgentAuditLogger, @audit_step, PII/metric guardrails
14. test+feat: LangGraph orchestrator with sequential flow
15. test+feat: final metric queries validated against real data
16. feat: streamlit UI with metrics, charts, report and audit expander
17. docs: README, architecture diagram, final review
18. chore: code cleanup, type hints, ruff
```

---

## Como usar este plano vs. `improvements_plan.md`

- **Durante o sprint:** seguir este arquivo até o fim sem desviar.
- **Se quebrar:** consultar riscos acima (ex: LLM falha → trocar `LLM_PROVIDER` no `.env`).
- **Após entrega:** se houver folga, executar `improvements_plan.md` na ordem de prioridade da tabela "Resumo" daquele arquivo.
- **README final:** copiar tabela de prioridades de `improvements_plan.md` como seção "Melhorias Futuras" — demonstra maturidade técnica sem precisar implementar.
