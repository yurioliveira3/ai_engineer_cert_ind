# Core Foundations — SRAG AI Agent
> **Entregável:** banco populado, LLM respondendo, SQL tool com guardrails, pipeline de embeddings e prompts versionados. Nenhuma feature do agente ainda.
> **Sequência:** este arquivo → `core_evolution.md` → `improvements_plan.md`
> **Histórico de decisões:** `adr.md`

---

## Princípios de desenvolvimento

Estes princípios valem para todo o projeto — Foundations, Evolution e qualquer item de `improvements_plan.md`.

### TDD — testes primeiro, sempre

Cada componente segue o ciclo: escrever o teste (vermelho) → implementar o mínimo para passar (verde) → refatorar se necessário → commit. Nenhum módulo vai para commit sem testes passando. A ordem nos planos reflete isso: seções `X.T` vêm antes das seções `X`.

### Sem over-engineering

- Implementar o que o plano pede, nada além. Uma feature não pedida não entra, mesmo que "pareça útil".
- Três linhas similares é melhor que uma abstração prematura. Só extrair abstração quando houver pelo menos 3 casos reais de uso, não antecipados.
- Sem parâmetros de configuração para cenários hipotéticos. Se não há um caso concreto agora, não há variável de ambiente para ele.
- Sem tratamento de erro para cenários impossíveis. Código interno e garantias do framework são confiáveis — validar apenas nas fronteiras do sistema (input do usuário, APIs externas).

### Código limpo sem burocracia

- Nomes descritivos eliminam a necessidade de comentários. Só comentar o **porquê** quando há uma restrição não-óbvia, um workaround ou um invariante sutil.
- Sem docstrings explicando o que a função faz — o nome já diz. Docstrings apenas quando o contrato (parâmetros, retorno, exceções) não for auto-evidente.
- Type hints em todos os parâmetros e retornos de funções públicas.
- `ruff` como linter e formatter — rodar antes de cada commit.

### Escopo dos planos

- `core_foundations.md` e `core_evolution.md` são o CORE. Nenhum item de `improvements_plan.md` entra antes do CORE estar entregue e com testes verdes.
- Se surgir uma ideia nova durante a implementação: anotar em `improvements_plan.md` e seguir em frente.

---

## Fase 0 — Setup & Infraestrutura

**Objetivo:** Ambiente rodando, dependências instaladas, conexões validadas.

### 0.1 — Estrutura do repositório

- [ ] Criar `srag-agent/`, inicializar git
- [ ] `.gitignore`: `.env`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `data/raw/`, `.venv/`, `data/charts/`, `data/reports/`, `data/logs/`, `data/hf_cache/`
- [ ] Estrutura de diretórios:
  ```
  srag-agent/
  ├── docker-compose.yml
  ├── Dockerfile
  ├── .env.example
  ├── .gitignore
  ├── README.md
  ├── requirements.txt
  ├── pyproject.toml
  ├── src/
  │   ├── config.py
  │   ├── llm/
  │   │   ├── adapter.py
  │   │   └── providers.py
  │   ├── data/
  │   │   ├── etl.py
  │   │   ├── models.py
  │   │   ├── queries.py
  │   │   └── embeddings.py
  │   ├── agent/
  │   │   ├── orchestrator.py
  │   │   ├── tools/
  │   │   │   ├── sql_tool.py
  │   │   │   ├── news_tool.py
  │   │   │   ├── chart_tool.py
  │   │   │   └── report_tool.py
  │   │   ├── prompts/
  │   │   │   ├── __init__.py
  │   │   │   ├── system.txt
  │   │   │   ├── analyze_metrics.txt
  │   │   │   └── news_query_gen.txt
  │   │   ├── guardrails.py
  │   │   └── logging_config.py
  │   └── ui/
  │       └── app.py
  ├── tests/
  │   ├── conftest.py
  │   ├── test_etl.py
  │   ├── test_llm_adapter.py
  │   ├── test_sql_tool.py
  │   ├── test_guardrails.py
  │   ├── test_embeddings.py
  │   ├── test_news_tool.py
  │   ├── test_chart_tool.py
  │   ├── test_report_tool.py
  │   ├── test_orchestrator.py
  │   └── test_metrics.py
  ├── data/
  │   ├── raw/
  │   ├── charts/
  │   ├── reports/
  │   ├── logs/
  │   └── hf_cache/          # gitignored; cache do modelo HuggingFace (~1.3GB)
  ├── db/
  │   └── init-scripts/
  │       ├── 01_schemas.sql
  │       ├── 02_lang_setup.sql
  │       ├── 03_app_user.sql
  │       ├── 04_audit.sql
  │       └── 05_news.sql    # tabela news.news_embeddings + índice ivfflat
  ├── docs/
  │   ├── architecture.drawio
  │   ├── architecture.pdf
  │   ├── data_privacy.md
  │   ├── metrics_validation.md
  │   └── llm_test_results.md
  └── scripts/
      ├── seed_db.py
      ├── validate_data.py
      ├── test_llm.py
      └── run_agent.py
  ```
- [ ] Primeiro commit: `chore: initial project structure`

---

### 0.2 — Docker Compose

- [ ] `Dockerfile`: base `python:3.11-slim`, instalar `build-essential libpq-dev`, copiar e instalar `requirements.txt`, copiar `src/`
- [ ] `docker-compose.yml` com 2 serviços:
  - `db`: `pgvector/pgvector:pg16`, porta `5433:5432`, volume `pgdata` persistente, healthcheck `pg_isready -U $POSTGRES_USER`
  - `app`: build local, porta `8501:8501`, bind mount `./src`, `./data`, `./scripts`, depends_on `db` (service_healthy), env `HF_HOME=/data/hf_cache`, volume `./data/hf_cache:/data/hf_cache`
- [ ] Init scripts em `db/init-scripts/` (executados em ordem alfabética no primeiro boot):
  - `01_schemas.sql`: `CREATE SCHEMA IF NOT EXISTS srag; news; audit;`
  - `02_lang_setup.sql`: `CREATE EXTENSION IF NOT EXISTS vector;`
  - `03_app_user.sql`: role `srag_app` com grants SELECT/INSERT/UPDATE nos 3 schemas (sem DDL)
  - `04_audit.sql`: schema de auditoria completo — detalhado na **seção 2.8** abaixo; criar o arquivo agora
  - `05_news.sql`: tabela `news.news_embeddings` + índice ivfflat — detalhado abaixo em **2.3**; criar o arquivo agora, pois o banco precisa da tabela já no primeiro boot
- [ ] Montar via volume: `./db/init-scripts:/docker-entrypoint-initdb.d`
- [ ] Validar: `docker compose up --build` → ambos "Up", `SELECT * FROM pg_extension WHERE extname = 'vector';` retorna linha

**Armadilha:** `psycopg2` precisa de `libpq-dev`. Alternativa: `psycopg2-binary` no requirements (aceitável para PoC).

---

### 0.3 — Dependências Python e configuração

- [ ] `requirements.txt`:
  ```
  langchain>=0.3
  langchain-google-genai>=4.0
  langchain-openai>=0.3
  langchain-community>=0.3
  langchain-huggingface>=0.2
  langgraph>=0.4
  sqlalchemy>=2.0
  psycopg2-binary
  pgvector
  langchain-postgres>=0.0.12
  pandas>=2.0
  sentence-transformers>=3.0
  duckduckgo-search
  tavily-python
  plotly>=5.0
  kaleido
  fpdf2
  streamlit>=1.30
  python-dotenv
  pydantic>=2.0
  pydantic-settings
  pytest
  pytest-asyncio
  ruff
  ```
- [ ] `src/config.py` — `Settings(BaseSettings)`:
  - Campos: `database_url`, `llm_provider` (default `"gemini"`), `llm_api_key`, `llm_base_url`, `llm_model`, `embedding_model` (default `"BAAI/bge-large-en-v1.5"`), `embedding_dim` (default `1024`), `log_level`
  - `model_config = SettingsConfigDict(env_file=".env", extra="ignore")`
- [ ] `.env.example`:
  ```env
  DATABASE_URL=postgresql://srag_app:srag_pass@db:5432/srag
  LLM_PROVIDER=gemini
  LLM_MODEL=gemini-2.5-flash
  LLM_API_KEY=your_api_key_here
  # LLM_BASE_URL=   # Apenas para OpenAI-compatible (OpenRouter, Groq, Ollama)
  EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
  EMBEDDING_DIM=1024
  LOG_LEVEL=INFO
  ```
- [ ] Criar `.env` local (fora do git) com credenciais reais
- [ ] Validar: `from src.config import Settings; print(Settings().model_dump())`

---

### 0.4 — Validação de conectividade LLM *(caminho crítico)*

> **Pré-requisito:** implementar a **Fase 2.1** (LLM Adapter) antes de executar esta etapa. O script abaixo depende de `get_chat_model()` definido em `src/llm/adapter.py`. A ordem real de execução é: `0.3 → 2.1 → 0.4`.

- [ ] `scripts/test_llm.py`:
  - Instanciar via `get_chat_model(Settings())`
  - Chamada simples: "Olá, responda em uma frase curta em português"
  - Chamada com tool calling: definir tool `get_current_date`, verificar `response.tool_calls` populado, executar a tool, verificar resposta final
  - Documentar resultado em `docs/llm_test_results.md`
- [ ] Se tool calling falhar no provider default: trocar `LLM_PROVIDER` no `.env` para `openrouter` ou `groq` — sem mudar código

**Commit:** `feat: project setup with docker, config and LLM validation`

---

## Fixtures compartilhadas (`tests/conftest.py`)

Criar antes de qualquer teste. Fixtures mínimas obrigatórias:

- `test_settings` (`scope="session"`) — `Settings` lendo `.env.test` (aponta para banco de teste)
- `db_engine` (`scope="session"`) — engine SQLAlchemy usando `test_settings.database_url`
- `rollback_after_test` (`autouse=True`) — abre transação, cede `conn` ao teste, faz rollback ao final (banco limpo entre testes)
- `sample_srag_csv(tmp_path)` — gera CSV sintético com ~20 linhas em `tmp_path` (separador `;`, encoding `latin-1`, colunas mínimas: `DT_NOTIFIC`, `CLASSI_FIN`, `EVOLUCAO`, `UTI`, `VACINA_COV`, `NU_IDADE_N`, `CS_SEXO`, `SG_UF_NOT`)

> Testes marcados com `@pytest.mark.integration` requerem o CSV real em `data/raw/` e o banco populado. Os demais usam `sample_srag_csv` e rodam sempre, inclusive em CI.

---

## Fase 1 — Data Engineering (ETL)

**Objetivo:** Dados SRAG limpos no PostgreSQL, queries de validação passando, testes verdes.
**Ordem:** escrever testes → implementar → verde → avançar.

### 1.T — Testes primeiro (`tests/test_etl.py`)

**Unitários** (usam `sample_srag_csv` — rodam sem CSV real):
- [ ] `test_selected_columns_exist` — `SELECTED_COLUMNS` existem no DataFrame
- [ ] `test_date_conversion` — colunas `DT_*` convertidas para `datetime64` sem NaT inesperados
- [ ] `test_no_pii_columns` — `NM_PACIENT`, `NU_CPF`, `NU_CNS`, `NM_MAE_PAC` não existem no DataFrame final
- [ ] `test_no_duplicates` — duplicatas abaixo de threshold (< 1%)
- [ ] `test_label_columns_created` — `evolucao_label`, `caso_confirmado`, `ano_notificacao` existem

**Integração** (`@pytest.mark.integration` — requerem CSV real em `data/raw/`):
- [ ] `test_csv_loads_without_errors` — CSV real carrega com encoding e separador corretos
- [ ] `test_row_count` — > 100K linhas após tratamento com dados reais

---

### 1.1 — Download manual e exploração inicial

- [ ] Baixar CSV em https://dadosabertos.saude.gov.br/dataset/srag-2019-a-2026 → `data/raw/`
- [ ] Documentar no README: URL exata, data do download, arquivos baixados (quais anos)
- [ ] `scripts/explore_data.py`: testar encodings (`latin-1`, `utf-8`, `cp1252`), separadores (`;`, `,`), rodar `df.shape`, `df.dtypes`, `df.isnull().sum()`, `df['DT_NOTIFIC'].value_counts()`, `df.columns.tolist()`
- [ ] Baixar dicionário SIVEP-Gripe → `docs/dicionario_dados_sivep.pdf` (entender códigos de `EVOLUCAO`, `UTI`, `CLASSI_FIN`, `VACINA_COV`)

---

### 1.2 — Seleção de colunas relevantes

Criar constante `SELECTED_COLUMNS` em `src/data/etl.py`:

| Métrica | Colunas |
|---------|---------|
| Aumento de casos | `DT_NOTIFIC`, `DT_SIN_PRI`, `CLASSI_FIN` |
| Mortalidade | `EVOLUCAO`, `DT_EVOLUCA`, `CLASSI_FIN` |
| UTI | `UTI`, `DT_ENTUTI`, `DT_SAIDUTI` |
| Vacinação | `VACINA_COV`, `DOSE_1_COV`, `DOSE_2_COV` |
| Segmentação | `NU_IDADE_N`, `CS_SEXO`, `SG_UF_NOT`, `SEM_NOT` |
| Contexto | `DT_INTERNA`, `HOSPITAL` |

---

### 1.3 — Tratamento e limpeza

- [ ] Converter colunas `DT_*` para `datetime64` com `errors='coerce'`; logar % de sucesso por coluna
- [ ] Mapear códigos para labels (manter coluna numérica original + criar `_label`):
  - `EVOLUCAO`: 1→Cura, 2→Óbito SRAG, 3→Óbito outras causas, 9→Ignorado
  - `UTI` e `VACINA_COV`: 1→Sim, 2→Não, 9→Ignorado
  - `CS_SEXO`: M→Masculino, F→Feminino, I→Ignorado
- [ ] PII: verificar e deletar imediatamente se existirem `NM_PACIENT`, `NU_CPF`, `NU_CNS`, `NM_MAE_PAC`, `END_*`. Documentar decisões em `docs/data_privacy.md`
- [ ] Campos com risco de reidentificação (`ID_MN_RESI`, `CS_RACA`, `NU_IDADE_N`): manter, mas agregar em outputs (nunca retornar registros individuais)
- [ ] Criar `caso_confirmado = CLASSI_FIN.isin([1,2,3,4,5])`
- [ ] Criar `ano_notificacao = dt_notific.dt.year`
- [ ] Não deletar linhas com nulos — registrar % de nulos por coluna em log

---

### 1.4 — Modelagem e carga no PostgreSQL

- [ ] `src/data/models.py` — `SragCase(Base)`:
  ```python
  class SragCase(Base):
      __tablename__ = 'srag_cases'
      __table_args__ = {'schema': 'srag'}
      id               = Column(Integer, primary_key=True, autoincrement=True)
      dt_notific       = Column(Date, index=True)
      dt_sin_pri       = Column(Date)
      dt_interna       = Column(Date)
      evolucao         = Column(SmallInteger)
      evolucao_label   = Column(String(30))
      dt_evoluca       = Column(Date)
      uti              = Column(SmallInteger)
      dt_entuti        = Column(Date)
      dt_saiduti       = Column(Date)
      vacina_cov       = Column(SmallInteger)
      dose_1_cov       = Column(Date)
      dose_2_cov       = Column(Date)
      nu_idade_n       = Column(SmallInteger)
      cs_sexo          = Column(String(1))
      sg_uf_not        = Column(String(2), index=True)
      classi_fin       = Column(SmallInteger)
      caso_confirmado  = Column(Boolean, index=True)
      sem_not          = Column(SmallInteger)
      ano_notificacao  = Column(SmallInteger, index=True)
  ```
- [ ] Índice composto: `(dt_notific, caso_confirmado)` — query mais comum
- [ ] `scripts/seed_db.py`: `Base.metadata.create_all(engine)` → `df.to_sql(..., chunksize=5000, if_exists='replace')` → `ANALYZE srag.srag_cases;`
- [ ] Validar: `SELECT COUNT(*) FROM srag.srag_cases` > 100K, `SELECT DISTINCT ano_notificacao ... ORDER BY 1` mostra todos os anos

---

### 1.5 — Queries de validação

- [ ] `scripts/validate_data.py` com sanity checks:
  - Distribuição por ano
  - Nulos por coluna crítica
  - Taxa de mortalidade bruta (esperado: 15-25%)
  - Taxa UTI (esperado: 20-40%)
  - Taxa vacinação a partir de 2021
  - `SELECT MAX(dt_notific) FROM srag.srag_cases` — **anotar esta data como `data_ref`** (usar nas métricas em vez de `NOW()`)
- [ ] `python scripts/validate_data.py > docs/data_validation_results.txt`

**Commit:** `feat: ETL pipeline with data validation and tests`

---

## Fase 2 — Foundations do Core Agent

**Objetivo:** LLM adapter, SQL tool com guardrails, pipeline de embeddings e prompts versionados — cada um com testes verdes antes de avançar.

### 2.1 — LLM Adapter

#### 2.1.T — Testes primeiro (`tests/test_llm_adapter.py`)

- [ ] `test_get_chat_model_gemini` — instancia sem erro com `LLM_PROVIDER=gemini`
- [ ] `test_get_chat_model_dispatch` — trocar provider via `Settings` retorna classe diferente
- [ ] `test_get_embeddings_returns_singleton` — duas chamadas retornam a mesma instância
- [ ] `test_safe_invoke_retries_on_rate_limit` — simular `ResourceExhausted`, verificar N retries com backoff
- [ ] `test_safe_invoke_raises_after_max_retries` — após esgotar retries, levanta exceção
- [ ] `test_tool_calling_returns_tool_calls` — response tem `tool_calls` populado (integração real com provider)

---

- [ ] `src/llm/providers.py` — dicionário `PROVIDERS`:
  ```python
  PROVIDERS = {
      "gemini": {
          "class": "ChatGoogleGenerativeAI",
          "default_model": "gemini-2.5-flash",
          "requires_base_url": False,
          "extra_kwargs": {"thinking_budget": 0},
      },
      "openrouter": {
          "class": "ChatOpenAI",
          "base_url": "https://openrouter.ai/api/v1",
          "extra_headers": {"HTTP-Referer": "srag-agent", "X-Title": "SRAG Agent"},
      },
      "groq": {
          "class": "ChatOpenAI",
          "base_url": "https://api.groq.com/openai/v1",
      },
      "ollama": {
          "class": "ChatOpenAI",
          "base_url": "http://localhost:11434/v1",
          "requires_api_key": False,
      },
  }
  ```
- [ ] `src/llm/adapter.py`:
  - `get_chat_model(settings) -> BaseChatModel` — dispatch por `settings.llm_provider`, valida campos obrigatórios, loga `logger.info(f"LLM: {provider}/{model}")`
  - `get_embeddings(settings) -> Embeddings` — `HuggingFaceEmbeddings(BAAI/bge-large-en-v1.5)`, singleton cacheado em variável de módulo
  - `safe_invoke(model, prompt, retries=5, backoff_factor=2)` — captura `ResourceExhausted`, `RateLimitError`, status 429; backoff `2**attempt` segundos; após esgotar, `raise` com mensagem clara

---

### 2.2 — SQL Tool + Guardrails

#### 2.2.T — Testes primeiro (`tests/test_sql_tool.py`, `tests/test_guardrails.py`)

- [ ] `test_destructive_sql_blocked` — DROP, DELETE, UPDATE, INSERT retornam erro sem executar
- [ ] `test_ddl_blocked` — ALTER, TRUNCATE, CREATE, GRANT bloqueados
- [ ] `test_multi_statement_blocked` — `;` no meio da query bloqueado
- [ ] `test_select_star_without_where_blocked`
- [ ] `test_limit_auto_appended` — query sem LIMIT recebe `LIMIT 1000`
- [ ] `test_query_timeout_enforced` — query pesada interrompida pelo timeout de 10s
- [ ] `test_metric_query_returns_plausible_value` — cada um dos 6 templates retorna valor numérico não-nulo
- [ ] `test_audit_query_history_inserted` — `audit.query_history` recebe linha com hash e tempo a cada execução

---

- [ ] `src/data/queries.py` — 6 queries template com parâmetros `data_ref` e `uf` (opcional):
  - `QUERY_CASE_INCREASE_RATE` — semana atual vs semana anterior
  - `QUERY_MORTALITY_RATE` — `evolucao=2` / total com desfecho (`evolucao IN (1,2,3)`)
  - `QUERY_ICU_RATE` — `uti=1` / total internados confirmados
  - `QUERY_VACCINATION_RATE` — `vacina_cov=1` / total, filtro `ano_notificacao >= 2021`
  - `QUERY_DAILY_CASES_30D` — `GROUP BY dt_notific` últimos 30 dias
  - `QUERY_MONTHLY_CASES_12M` — `GROUP BY DATE_TRUNC('month', dt_notific)` últimos 12 meses

  Nota: usar `MAX(dt_notific)` do dataset como `data_ref` default, não `NOW()`.

- [ ] `src/agent/guardrails.py`:
  - `validate_sql_safety(query: str) -> tuple[bool, str]` — keywords proibidas, multi-statement, SELECT * sem WHERE
  - `safe_execute(query: str, params: dict, engine) -> tuple[pd.DataFrame | str, int]` — `statement_timeout=10s`, LIMIT auto, grava em `audit.query_history` com `sha256(normalize(query))`

  > `safe_execute` grava em `audit.query_history` com `session_id=NULL` (a referência é opcional). Quando o orquestrador (Fase 2.7 do Evolution) estiver ativo, o `AgentAuditLogger` sobrescreverá esse campo com o UUID da sessão. Isso permite que o Foundations funcione isoladamente sem depender do logger do agente.

- [ ] `src/agent/tools/sql_tool.py`:
  - `execute_metric_query(metric_name: str, params: dict) -> str` — chama `safe_execute`, formata resultado como string legível para o LLM

---

### 2.3 — Pipeline de Embeddings & RAG

#### 2.3.T — Testes primeiro (`tests/test_embeddings.py`)

- [ ] `test_embeddings_service_loads_model` — `EmbeddingsService` carrega sem erro
- [ ] `test_embed_query_returns_1024_dim` — vetor tem 1024 dimensões
- [ ] `test_upsert_idempotent` — 2 upserts da mesma URL não duplica linhas (`COUNT(*)` igual)
- [ ] `test_similarity_search_returns_topk` — retorna exatamente `k` resultados (ou menos se índice menor)
- [ ] `test_similarity_search_ordered_by_score` — primeiro resultado tem score >= último

---

> Schema da tabela `news.news_embeddings` está em `db/init-scripts/05_news.sql` (criado no Docker, Fase 0.2). Conteúdo do arquivo:
> ```sql
> CREATE TABLE news.news_embeddings (
>     id         SERIAL PRIMARY KEY,
>     url        TEXT UNIQUE NOT NULL,
>     title      TEXT,
>     snippet    TEXT,
>     source     TEXT,
>     query_used TEXT,
>     embedding  vector(1024),
>     indexed_at TIMESTAMP DEFAULT NOW()
> );
> CREATE INDEX news_embeddings_vec_idx
>   ON news.news_embeddings
>   USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
> ```

- [ ] `src/data/embeddings.py`:
  - `EmbeddingsService`: `embed_texts(list[str]) -> list[list[float]]`, `embed_query(str) -> list[float]` — singleton cacheado em variável de módulo (primeiro load ~10s)
  - `NewsEmbeddingsRepository(engine, embeddings_service)`:
    - `upsert(items: list[dict]) -> int` — `INSERT … ON CONFLICT (url) DO UPDATE`, retorna contagem
    - `similarity_search(query: str, k=5) -> list[dict]` — `ORDER BY embedding <=> :q LIMIT :k`, filtrar `score < 0.6`

**Armadilha:** `BAAI/bge-large-en-v1.5` ocupa ~1.3GB de RAM — cachear via volume Docker (`HF_HOME=/data/hf_cache`). Se scores PT-BR ficarem baixos, avaliar `BAAI/bge-m3` (multilingual, mesma dimensão).

---

### 2.4 — Prompts versionados (infraestrutura de governança)

- [ ] `src/agent/prompts/system.txt`, `analyze_metrics.txt`, `news_query_gen.txt` — template padrão em todos:
  ```
  ### Atue
  <persona/papel>

  ### Tarefa
  <objetivo específico>

  ### Público-alvo
  Profissionais de saúde com formação clínica (médicos, epidemiologistas, gestores hospitalares).
  Escreva com linguagem de saúde pública. Evite termos de engenharia de software, nomes de
  variáveis, tecnologias ou jargão de dados. Prefira: "internações por SRAG", "taxa de
  mortalidade hospitalar", "cobertura vacinal" — não "DataFrame", "query", "embedding".

  ### Temporalidade dos dados
  As métricas são baseadas em dados históricos do DATASUS (última atualização: {data_ref}).
  As notícias foram consultadas em tempo real ({data_hora_consulta}).
  Sempre que mencionar "situação atual", refira-se explicitamente ao período coberto pelos dados.

  ### Requisitos
  - Entrada: <estrutura do payload>
  - Saída: <formato, tom, restrições>

  ### Instruções
  1. <passos numerados>

  ### Restrições anti-alucinação
  - Não inventar números nem datas não presentes no payload
  - Citar URL ao referenciar notícia
  - Marcar explicitamente quando dado está ausente: "métrica indisponível no período"
  - Não emitir diagnósticos clínicos individuais (LGPD)

  ### Payload
  {payload}

  ### Exemplo de saída esperada
  <1-2 parágrafos de gold standard escritos no tom de saúde pública>
  ```
- [ ] `src/agent/prompts/__init__.py`:
  - `load_prompt(name: str) -> str` — lê arquivo `.txt`
  - `render_prompt(name: str, **kwargs) -> tuple[str, str]` — substitui placeholders, retorna `(prompt_rendered, sha256_hex)` para gravar em `audit.llm_calls`

---

### 2.8 — Schema de auditoria (`db/init-scripts/04_audit.sql`)

Criado no momento do Docker (referenciado em 0.2). O SQL completo vai no arquivo; estrutura das 4 tabelas para referência:

| Tabela | Campos principais |
|--------|------------------|
| `audit.agent_sessions` | `id UUID PK`, `created_at`, `finished_at`, `llm_provider`, `llm_model`, `status` (running/success/partial/failed), `error_text` |
| `audit.agent_decisions` | `id`, `session_id FK`, `step_name`, `tool_name`, `input_summary`, `output_summary`, `duration_ms`, `success` |
| `audit.query_history` | `id`, `session_id FK NULL`, `query_text`, `query_hash VARCHAR(64)`, `execution_time_ms`, `blocked`, `block_reason`, `db_user` |
| `audit.llm_calls` | `id`, `session_id FK`, `prompt_name`, `prompt_file`, `prompt_hash VARCHAR(64)`, `response_summary`, `tokens_input`, `tokens_output`, `duration_ms` |

Índices: `created_at DESC` em `agent_sessions`; `(session_id, created_at)` em `agent_decisions`; `session_id` e `query_hash` em `query_history`; `session_id` em `llm_calls`.

---

## Entregável do Foundations

Antes de avançar para `core_evolution.md`, confirmar todos os itens:

- [ ] `docker compose up --build` → ambos serviços "Up", pgvector ativo (`SELECT extname FROM pg_extension WHERE extname = 'vector'`), schemas e 4 tabelas `audit.*` criadas
- [ ] `python scripts/seed_db.py` → `SELECT COUNT(*) FROM srag.srag_cases` > 100K
- [ ] `python scripts/test_llm.py` → provider configurado responde, tool calling com `tool_calls` populado
- [ ] `pytest tests/test_etl.py tests/test_llm_adapter.py tests/test_sql_tool.py tests/test_guardrails.py tests/test_embeddings.py -v` → todos green
- [ ] `docs/data_privacy.md` documenta decisões sobre PII
- [ ] Nenhum campo PII no DataFrame final

**Commit:** `feat: foundations — ETL, LLM adapter, SQL tool, embeddings, audit schema`
