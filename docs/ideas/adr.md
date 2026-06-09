# ADR — SRAG AI Agent
> Architecture Decision Records: histórico de versões e decisões técnicas do `core_plan.md`.
> Não é plano de execução. Consultar para entender *por que* cada escolha foi feita.

---

## v3.2 — Arquitetura Provider-Agnostic (Jun 2026)

Motivação: sem desacoplamento, trocar de LLM requer reescrever o adapter. Com dispatch por `LLM_PROVIDER`, o mesmo código serve para qualquer provider.

| Mudança | Detalhe |
|---------|---------|
| `src/llm/providers.py` | Dicionário com configs de `gemini`, `openrouter`, `groq`, `ollama` |
| `src/llm/adapter.py` | `get_chat_model(settings)` despacha pela classe correta. Sem fallback automático (→ `improvements_plan.md`§2) |
| `safe_invoke` | Captura `ResourceExhausted` (Gemini), `RateLimitError` (OpenAI-compatible), status 429 |
| `.env.example` | `LLM_PROVIDER=gemini`, `LLM_BASE_URL` (apenas para OpenAI-compatible) |

---

## v3.1 — Gemini SDK & Modelo (Jun 2026)

| Mudança | Detalhe |
|---------|---------|
| `langchain-google-genai` 2.0 → 4.0+ | Migração para SDK consolidado `google-genai` |
| `gemini-1.5-flash` → `gemini-2.5-flash` | Tool calling robusto via `bind_tools()`, pensando desabilitável |
| `thinking_budget=0` | Desativa reasoning interno, economiza tokens no free tier |
| Nota Gemini 3.x | Se migrar: usar `thinking_level="minimal"` e preservar `AIMessage` original (não reconstruir) |

---

## v3 — Refatoração CORE vs. MELHORIAS

Versão anterior (v2.1) acumulou escopo excessivo após análise do `analytics_ql`. Divisão em dois arquivos:

| Item diferido | Motivo | Referência |
|---------------|--------|------------|
| Download automatizado DATASUS | Discovery via HTML frágil; manual basta para PoC | `improvements_plan.md`§1 |
| Multi-provider fallback automático | Complexidade de produção; dispatch no CORE resolve PoC | `improvements_plan.md`§2 |
| EXPLAIN-based cost gate | Queries são templates fixos; cost gate é polish | `improvements_plan.md`§3 |
| Hash integrity SHA-256 | Sem armazenamento intermediário, sem janela de tampering | `improvements_plan.md`§4 |
| Padrões avançados de SQL injection | Templates via SQLAlchemy já protegem | `improvements_plan.md`§5 |
| RAG com TTL + edge condicional | RAG simples atende o pré-requisito | `improvements_plan.md`§6 |
| First-layer router | UI não tem input livre na PoC | `improvements_plan.md`§7 |
| Trendline OLS no gráfico | LLM já gera análise textual de tendência | `improvements_plan.md`§8 |
| Cobertura ampla de testes (>15/módulo) | Smoke tests bastam para PoC | `improvements_plan.md`§10 |
| Validação cruzada automatizada | Validação manual documentada basta | `improvements_plan.md`§11 |

---

## v2 — Ajustes após análise do `analytics_ql`

| Aspecto | v1 | v2 |
|---------|----|----|
| LLM primário | OpenCode Go (`glm-5`) | Gemini `gemini-2.5-flash` — free tier, tool calling validado |
| Adapter | OpenAI-compatible (4 providers) | Provider-agnostic dispatch via `LLM_PROVIDER` |
| RAG | pgvector instalado mas nunca usado | Pipeline de RAG para notícias com pgvector |
| Embedding model | `all-MiniLM-L6-v2` (384-dim) | `BAAI/bge-large-en-v1.5` (1024-dim) — mesmo do `analytics_ql` |
| Dataset | Download manual assumido | Script automatizado (depois diferido para improvements§1) |
| Repositório | — | Novo repo `srag-agent` separado do `analytics_ql` |

**Pontos que motivaram os ajustes:**
1. **Lacuna crítica de RAG** — instruções exigem "bancos vetoriais e RAG"; plano original instalava pgvector sem usar
2. **Lock-in de LLM** — mitigado com adapter provider-agnostic
3. **Distinção "taxa de UTI" vs. "ocupação de leitos"** — mantida e documentada; não temos dados de oferta de leitos
4. **`kaleido` e `fpdf2` UTF-8** — riscos conhecidos com fallbacks definidos
5. **Cache de LLM** — diferido para improvements§13

---

## Reaproveitamento do `analytics_ql`

Estratégia: **copiar padrões, não código direto** — arquiteturas diferentes (Flask + NL→SQL vs. LangGraph + agente especializado).

| Componente | De (`analytics_ql`) | Para (`srag-agent`) |
|------------|--------------------|--------------------|
| Setup pgvector Docker | `Database/docker-compose.yml` | `docker-compose.yml` |
| Init scripts Postgres | `Database/init-scripts/lang_setup.sql` | `db/init-scripts/02_lang_setup.sql` |
| User/permissão DB | `Database/init-scripts/app_user.sql` | `db/init-scripts/03_app_user.sql` |
| Schema de auditoria | `Database/init-scripts/metadata.sql` | `db/init-scripts/04_audit.sql` |
| SQL safety básico | `App/utils/query_protection.py` | `src/agent/guardrails.py` |
| Chart base | `App/utils/chart_generator.py` | `src/agent/tools/chart_tool.py` |
| Embeddings + pgvector | `Engine/lang/chain.py` | `src/data/embeddings.py` |
| Config + DB | `App/utils/config.py` | `src/config.py` |
| Logger estruturado | `App/utils/logger.py` | `src/agent/logging_config.py` |
| Prompts versionados em `.txt` | `App/prompts/insights_generation.txt` | `src/agent/prompts/` |
| Safe LLM call | `App/utils/llm_utils.safe_send_message` | `src/llm/adapter.py::safe_invoke` |
| Insights payload pattern | `llm_utils.generate_insights_payload` | `src/agent/orchestrator.py` nó `analyze` |
| Test pattern proteção | `Test/test_protection.py` | `tests/test_guardrails.py` |

**Não reaproveitado:** Flask app, Gemini SDK direto, Engine de DDL, NL→SQL pipeline, chat sessions persistidas.
