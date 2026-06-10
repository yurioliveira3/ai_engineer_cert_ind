# SRAG AI Agent

Agente de IA para análise automatizada de dados epidemiológicos de SRAG (Síndrome Respiratória Aguda Grave) com geração de relatórios, usando dados abertos do DATASUS.

## Visão Geral

O SRAG Agent é um sistema que combina dados epidemiológicos históricos do DATASUS/SIVEP-Gripe com busca de notícias em tempo real para gerar relatórios analíticos em linguagem acessível a profissionais de saúde. O agente segue um fluxo sequencial de 6 etapas: métricas → gráficos → notícias → busca semântica → análise LLM → relatório.

```
START → calculate_metrics → generate_charts → search_news → retrieve_semantic → analyze → compile_report → END
```

Cada etapa é auditada com `AgentAuditLogger`, e guardrails protegem contra injeção de prompt, injeção de SQL e vazamento de PII.

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                     SRAG Agent (LangGraph)                  │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  SQL Tool     │  │  News Tool   │  │  Chart Tool  │      │
│  │ (4 métricas + │  │  (DuckDuckGo)│  │  (Plotly)    │      │
│  │  2 temporais) │  │              │  │              │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                   │             │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐      │
│  │  PostgreSQL   │  │   pgvector   │  │  PNG export  │      │
│  │  + pgvector   │  │  embeddings  │  │  (kaleido)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Report Tool   │  │  LLM Adapter │  │  Audit Logger│      │
│  │  (MD + PDF)   │  │ (provider-   │  │  (4 tabelas  │      │
│  │  (fpdf2)      │  │  agnostic)   │  │   audit.*)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                             │
│  ┌──────────────────────────────────────────────────┐       │
│  │              Guardrails & Logging                │       │
│  │  • SQL safety (keywords, LIMIT)                  │       │
│  │  • Input validation (injection detection)        │       │
│  │  • Output PII filter (CPF, phone, email)         │       │
│  │  • Metric range warnings                        │       │
│  └──────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## Stack Tecnológica

| Ferramenta | Versão | Propósito | Justificativa |
|-----------|---------|-----------|---------------|
| Python | 3.11+ | Linguagem principal | Ecossistema rico para dados e IA |
| PostgreSQL + pgvector | 16 | Banco de dados com busca vetorial | SQL + embeddings no mesmo banco |
| LangGraph | 0.4+ | Orquestração do agente | Fluxo sequencial com estado tipado |
| LangChain | 0.3+ | Framework LLM | Provider-agnostic, tool calling |
| Gemini 2.5 Flash | default | LLM provider | Custo-benefício, tool calling estável |
| HuggingFace BGE | bge-large-en-v1.5 | Embeddings (1024-dim) | Busca semântica em notícias |
| DuckDuckGo (`ddgs`) | — | Busca de notícias | Gratuito, sem API key; termo regionalizável por UF |
| Plotly + kaleido | 5.0+ | Gráficos | Interativo no Streamlit, estático no PDF |
| fpdf2 | — | Geração de PDF | Leve, suporte UTF-8 |
| Streamlit | 1.30+ | Interface web | Dashboard com métricas, gráficos, relatório e auditoria |
| SQLAlchemy | 2.0+ | ORM e queries | Conexão com PostgreSQL |
| Pydantic | 2.0+ | Configuração | Validação de settings |

## Início Rápido

### Pré-requisitos

- Python 3.11+
- Docker e Docker Compose
- Chave de API do Google (Gemini) ou outro provider LLM

### Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/yurioliveira3/ai_engineer_cert_ind.git
cd ai_engineer_cert_ind

# 2. Copie e configure o .env
cp .env.example .env
# Edite .env e adicione sua LLM_API_KEY

# 3. Suba o PostgreSQL com pgvector
docker compose up -d srag-db

# 4. Instale as dependências
pip install -e .

# 5. Baixe os dados do DATASUS
python scripts/download_srag_data.py --all

# 6. Carregue os dados no banco
python scripts/seed_db.py

# 7. Valide os dados
python scripts/validate_data.py

# 8. Teste a conectividade LLM
python scripts/test_llm.py

# 9. Execute o agente via CLI
python scripts/run_agent.py

# 10. Ou inicie a interface web
streamlit run src/ui/app.py

# Docker (opcional)
docker compose up -d
```

### Operações Docker

**Recriar só o app** (preserva o banco e os dados):

```bash
docker compose stop srag-app
docker compose build --no-cache srag-app
docker compose up -d srag-app
```

**Recriar tudo do zero** (apaga banco e dados — requer seed após subir):

```bash
docker compose down -v          # para containers e apaga volumes (incluindo srag-pgdata)
docker compose build --no-cache
docker compose up -d
python scripts/seed_db.py       # recarrega os dados no banco
```

> ⚠️ `down -v` apaga o volume `srag-pgdata`. Todos os dados do PostgreSQL são perdidos.

**Verificar logs:**

```bash
docker compose logs -f srag-app
docker compose logs -f srag-db
```

### Configuração (.env)

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `POSTGRES_USER` | `srag_app` | Usuário do PostgreSQL |
| `POSTGRES_PASSWORD` | `srag_pass` | Senha do PostgreSQL |
| `POSTGRES_DB` | `srag` | Nome do banco |
| `POSTGRES_PORT` | `5433` | Porta local para acesso ao banco |
| `DATABASE_URL` | construído dinamicamente | URL completa do PostgreSQL (usa as variáveis acima) |
| `LLM_PROVIDER` | `gemini` | Provider LLM (gemini, openrouter, groq, ollama) |
| `LLM_MODEL` | `gemini-2.5-flash` | Modelo LLM |
| `LLM_API_KEY` | — | Chave de API do provider |
| `LLM_BASE_URL` | — | URL base para providers OpenAI-compatible |
| `GOOGLE_API_KEY` | — | Alternativa: define a chave do Google se `LLM_API_KEY` estiver vazio |
| `EMBEDDING_MODEL` | `BAAI/bge-large-en-v1.5` | Modelo de embeddings |
| `EMBEDDING_DIM` | `1024` | Dimensão dos embeddings |
| `LOG_LEVEL` | `INFO` | Nível de log |
| `NEWS_MAX_SEARCHES` | `3` | Lido pelo Settings, mas o orquestrador usa `max_results=5` fixo no `search_news_step` |

## Dados

### Fonte

Dados epidemiológicos de SRAG do DATASUS/SIVEP-Gripe, baixados diretamente do S3:
- URL: `https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/`
- Período: 2023-2026
- **604.230 registros** carregados

### Temporalidade dos dados

- **Métricas e gráficos**: derivados dos dados históricos do DATASUS — a cobertura vai até a data mais recente disponível no dataset (`MAX(dt_notific)`). O agente usa esta data como referência, não `NOW()`.
- **Notícias**: consultadas em tempo real via DuckDuckGo a cada execução do agente.
- Esta distinção é exibida no relatório gerado e nos prompts do LLM.

### Métricas

| Métrica | Fórmula | Observação |
|---------|---------|------------|
| Taxa de aumento de casos | `(casos_semana_atual - casos_semana_anterior) / casos_semana_anterior × 100` | Semana a semana |
| Taxa de mortalidade | `óbitos SRAG / total com desfecho × 100` | Apenas casos com evolução 1, 2 ou 3 |
| Taxa de UTI | `internados em UTI / total internados × 100` | Proporção de internados que foram para UTI, não ocupação de leitos |
| Taxa de vacinação | `vacinados / total de casos × 100` | A partir de 2021 (ano de início da vacinação) |

> **Nota:** A taxa de UTI é a proporção de internados que foram para UTI, não a ocupação de leitos. Ocupação de leitos não está disponível no SIVEP-Gripe.

> **Nota:** A taxa de aumento de casos não tem base percentual quando a semana anterior tem 0 casos (comum perto do `MAX(dt_notific)`, onde os dados ainda são esparsos por atraso de notificação). Nesse caso, a interface e o relatório exibem a **variação absoluta** (ex.: `+127 casos`) em vez de um percentual. Quando ambas as semanas têm 0 casos, o valor é `0,00%`.

### Privacidade dos dados

Veja [docs/data_privacy.md](docs/data_privacy.md) para detalhes sobre:
- Colunas PII removidas (NM_PACIENT, NU_CPF, NU_CNS, NM_MAE_PAC, END_*)
- Colunas retidas apenas com agregação (NU_IDADE_N, ID_MN_RESI, CS_RACA)
- Conformidade com LGPD
- Guardrails de output (filtro de CPF, telefone, email)

## Filtros e parâmetros

### Filtros da interface (UF e data de referência)

A sidebar do Streamlit oferece dois filtros que são propagados de ponta a ponta (UI → `run_agent` → estado do agente → queries):

- **UF (Unidade Federativa)**: filtra os dados por estado de notificação (`sg_uf_not`). `Todos` considera o Brasil inteiro. Aplica-se às métricas, aos gráficos e, como contexto, ao termo de busca de notícias (ex.: `SRAG São Paulo epidemiologia`).
- **Data de referência**: quando informada, é usada como `data_ref` nas janelas das queries; quando vazia, usa-se `MAX(dt_notific)` do escopo selecionado (global ou da UF).

> As notícias são buscadas na web (DuckDuckGo) e, embora o termo seja regionalizado pela UF, não há filtro geográfico rígido — elas funcionam como contexto qualitativo.

### Parâmetros de geração do LLM

Ajustados para análise factual e ancorada (dados + notícias), não geração criativa. Definidos por provider em `src/llm/providers.py` e exibidos no expander de auditoria da UI (via `get_sampling_params`):

| Parâmetro | Valor | Observação |
|-----------|-------|------------|
| `temperature` | `0.2` | Baixa, mais determinística |
| `top_p` | `0.85` | Nucleus sampling reduzido |
| `top_k` | `20` | Apenas Gemini (não faz parte da API OpenAI padrão) |

O uso de tokens de cada chamada LLM é extraído do `usage_metadata` do provider (com estimativa de fallback) e registrado em `audit.llm_calls` e nos logs.

## Guardrails

O agente implementa 4 camadas de proteção:

1. **Validação de input SQL**: palavras-chave destrutivas bloqueadas (DROP, DELETE, etc.), multi-statement bloqueado, SELECT * sem WHERE bloqueado, LIMIT automático (padrão 1000)
2. **Validação de input do usuário**: limite de 1000 caracteres, detecção de injeção de prompt (7 padrões em PT e EN), sanitização de caracteres especiais
3. **Validação de métricas**: alertas para mortalidade > 50%, UTI > 100%, vacinação > 100%, aumento > 500%
4. **Filtro de PII no output**: mascaramento de CPF (XXX.XXX.XXX-XX), telefone e email

**Busca de notícias**: DuckDuckGo com `region="br-pt"`, máximo de 5 resultados por busca, classificação automática de fontes (confiáveis vs. não-verificadas), rate limiting (`max_results > 5` rejeitado).

Todas as queries SQL são logadas em `audit.query_history` com hash SHA-256. Cada execução do agente cria uma sessão auditada com logs de decisão em `audit.agent_decisions` e chamadas LLM em `audit.llm_calls`.

### Observabilidade (logging)

Além da auditoria no banco, o `AgentAuditLogger` emite um **trace verboso** no console e em arquivo rotativo diário (`data/logs/srag_agent.log`). O `setup_logger` configura o logger-raiz do pacote (`src`) com `propagate=False` (evita duplicação sob o Streamlit) e silencia bibliotecas ruidosas. O trace mostra o fluxo de tool calls do agente — início de cada nó, `[tool-call]` (step/ferramenta/status/duração), `[llm-call]` (prompt/hash/tokens) e `[sql]` —, controlado por `LOG_LEVEL`.

## Testes

```bash
# Testes unitários (sem banco/CVS reais)
pytest tests/ -v -m "not integration"

# Testes de integração (requer banco populado e CSV em data/raw/)
pytest tests/ -v -m integration

# Todos os testes
pytest tests/ -v

# Lint e formatação
ruff check src/ tests/ scripts/
ruff format src/ tests/ scripts/
```

**Resultados atuais:** 102 testes unitários + 19 de integração = 121 total, 0 erros, ruff limpo (regras: E, F, I, N, W, UP, B, SIM, T20, RUF).

## Estrutura do Projeto

```
srag-agent/
├── docker-compose.yml          # PostgreSQL + pgvector (porta 5433)
├── Dockerfile                  # Container da aplicação (porta 8501)
├── requirements.txt            # Dependências Python
├── pyproject.toml              # Configuração do projeto (ruff, pytest)
├── .env.example                # Template de variáveis de ambiente
├── db/init-scripts/            # 5 scripts SQL de inicialização
│   ├── 01_schemas.sql         # Schemas: srag, news, audit
│   ├── 02_lang_setup.sql      # Extensão pgvector
│   ├── 03_app_user.sql        # Role srag_app com grants
│   ├── 04_audit.sql           # 4 tabelas de auditoria
│   └── 05_news.sql            # news_embeddings com índice ivfflat
├── src/
│   ├── config.py              # Settings (Pydantic BaseSettings)
│   ├── llm/
│   │   ├── adapter.py         # get_chat_model, get_embeddings, safe_invoke, get_token_usage
│   │   └── providers.py       # Providers + sampling factual (temperature/top_p/top_k), get_sampling_params
│   ├── data/
│   │   ├── etl.py             # CSV load, clean, PII removal, labels
│   │   ├── models.py          # SragCase SQLAlchemy model
│   │   ├── queries.py         # 6 SQL templates parametrizados (data_ref + filtro :uf opcional)
│   │   └── embeddings.py      # EmbeddingsService + NewsEmbeddingsRepository (CAST :embedding AS vector)
│   ├── agent/
│   │   ├── orchestrator.py    # LangGraph StateGraph (SRAGAgent); filtros UF/data, news regional, setup do logging
│   │   ├── guardrails.py      # SQL safety, input/output validation, PII filter
│   │   ├── logging_config.py  # AgentAuditLogger (trace verboso), setup_logger
│   │   ├── prompts/
│   │   │   ├── __init__.py    # load_prompt, render_prompt (SHA-256)
│   │   │   ├── system.txt     # Prompt do sistema
│   │   │   ├── analyze_metrics.txt  # Prompt de análise
│   │   │   └── news_query_gen.txt   # Prompt de geração de queries
│   │   └── tools/
│   │       ├── sql_tool.py     # execute_metric_query, execute_tabular_query, get_data_ref (4 métricas + 2 temporais)
│   │       ├── news_tool.py    # search_and_index_news (ddgs, output_format=list), semantic_search_news
│   │       ├── chart_tool.py   # generate_daily/monthly_cases_chart (write_image tolerante a falha)
│   │       └── report_tool.py  # generate_report (markdown + PDF), format_metric_value / metric_value_parts
│   └── ui/
│       └── app.py             # Dashboard Streamlit: filtros (UF/data), métricas, gráficos (Plotly), PDF, auditoria
├── tests/                      # 11 arquivos de teste, 121 testes
├── scripts/
│   ├── download_srag_data.py  # Download CSVs do DATASUS S3
│   ├── seed_db.py             # Carga no PostgreSQL
│   ├── validate_data.py       # Sanity checks
│   ├── explore_data.py        # Exploração de dados
│   ├── test_llm.py            # Validação de conectividade LLM
│   └── run_agent.py           # CLI runner do agente
└── docs/
    ├── data_privacy.md         # Decisões PII/LGPD
    └── metrics_validation.md   # Validação cruzada das métricas (Fase 3)
```

## Melhorias Futuras

Itens planejados para implementação posterior (detalhes em `docs/ideas/improvements_plan.md`):

| Prioridade | Item | Descrição |
|-----------|------|-----------|
| Alta | Cache de buscas | Evitar buscar notícias repetidas em execuções seguidas |
| Alta | Fallback Tavily | Busca de notícias quando DuckDuckGo falha |
| Média | Multi-agente | Arquitetura com especialistas (epidemiologista, vacinólogo) |
| Média | Embeddings multilingual | Avaliar BAAI/bge-m3 para melhor busca em PT-BR |
| Baixa | Download automático | Agendamento de atualização dos dados SRAG |
| Baixa | PDF customizado | Melhor layout com tabelas e gráficos embutidos |

## Licença

Projeto acadêmico para certificação de AI Engineer. Dados públicos do DATASUS (Portaria GM/MS No. 1.119/2022).