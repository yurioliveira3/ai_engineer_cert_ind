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
│  │  (6 metrics)  │  │  (DuckDuckGo)│  │  (Plotly)    │      │
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
│  │  • SQL safety (keywords, timeout, LIMIT)         │       │
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
| DuckDuckGo Search | — | Busca de notícias | Gratuito, sem API key |
| Plotly + kaleido | 5.0+ | Gráficos | Interativo no Streamlit, estático no PDF |
| fpdf2 | — | Geração de PDF | Leve, suporte UTF-8 |
| Streamlit | 1.30+ | Interface web | Planejado para Fase 4 |
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
docker compose up -d db

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
```

### Configuração (.env)

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `DATABASE_URL` | `postgresql://srag_app:srag_pass@db:5432/srag` | URL do PostgreSQL |
| `LLM_PROVIDER` | `gemini` | Provider LLM (gemini, openrouter, groq, ollama) |
| `LLM_MODEL` | `gemini-2.5-flash` | Modelo LLM |
| `LLM_API_KEY` | — | Chave de API do provider |
| `LLM_BASE_URL` | — | URL base para providers OpenAI-compatible |
| `GOOGLE_API_KEY` | — | Alternativa: define a chave do Google se `LLM_API_KEY` estiver vazio |
| `EMBEDDING_MODEL` | `BAAI/bge-large-en-v1.5` | Modelo de embeddings |
| `EMBEDDING_DIM` | `1024` | Dimensão dos embeddings |
| `LOG_LEVEL` | `INFO` | Nível de log |

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

### Privacidade dos dados

Veja [docs/data_privacy.md](docs/data_privacy.md) para detalhes sobre:
- Colunas PII removidas (NM_PACIENT, NU_CPF, NU_CNS, NM_MAE_PAC, END_*)
- Colunas retidas apenas com agregação (NU_IDADE_N, ID_MN_RESI, CS_RACA)
- Conformidade com LGPD
- Guardrails de output (filtro de CPF, telefone, email)

## Guardrails

O agente implementa 4 camadas de proteção:

1. **Validação de input SQL**: palavras-chave destrutivas bloqueadas (DROP, DELETE, etc.), multi-statement bloqueado, SELECT * sem WHERE bloqueado, timeout de 10s, LIMIT automático
2. **Validação de input do usuário**: limite de 1000 caracteres, detecção de injeção de prompt (7 padrões em PT e EN), sanitização de caracteres especiais
3. **Validação de métricas**: alertas para mortalidade > 50%, UTI > 100%, vacinação > 100%, aumento > 500%
4. **Filtro de PII no output**: mascaramento de CPF (XXX.XXX.XXX-XX), telefone e email

**Busca de notícias**: DuckDuckGo com `region="br-pt"`, máximo de 5 resultados por busca, classificação automática de fontes (confiáveis vs. não-verificadas), rate limiting (`max_results > 5` rejeitado).

Todas as queries SQL são logadas em `audit.query_history` com hash SHA-256. Cada execução do agente cria uma sessão auditada com logs de decisão em `audit.agent_decisions` e chamadas LLM em `audit.llm_calls`.

## Testes

```bash
# Testes unitários (sem banco/CVS reais)
pytest tests/ -v -k "not integration"

# Testes de integração (requer banco populado e CSV em data/raw/)
pytest tests/ -v -m integration

# Lint e formatação
ruff check src/ tests/ scripts/
ruff format src/ tests/ scripts/
```

**Resultados atuais:** 76 testes passando, 0 erros, ruff limpo.

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
│   │   ├── adapter.py         # get_chat_model, get_embeddings, safe_invoke
│   │   └── providers.py       # Dict de providers (gemini, openrouter, groq, ollama)
│   ├── data/
│   │   ├── etl.py             # CSV load, clean, PII removal, labels
│   │   ├── models.py          # SragCase SQLAlchemy model
│   │   ├── queries.py         # 6 SQL templates parametrizados
│   │   └── embeddings.py      # EmbeddingsService + NewsEmbeddingsRepository
│   ├── agent/
│   │   ├── orchestrator.py    # LangGraph StateGraph (SRAGAgent)
│   │   ├── guardrails.py      # SQL safety, input/output validation, PII filter
│   │   ├── logging_config.py  # AgentAuditLogger, @audit_step, setup_logger
│   │   ├── prompts/
│   │   │   ├── __init__.py    # load_prompt, render_prompt (SHA-256)
│   │   │   ├── system.txt     # Prompt do sistema
│   │   │   ├── analyze_metrics.txt  # Prompt de análise
│   │   │   └── news_query_gen.txt   # Prompt de geração de queries
│   │   └── tools/
│   │       ├── sql_tool.py     # execute_metric_query (6 métricas)
│   │       ├── news_tool.py    # search_and_index_news, semantic_search_news
│   │       ├── chart_tool.py   # generate_daily/monthly_cases_chart
│   │       └── report_tool.py  # generate_report (markdown + PDF)
│   └── ui/
│       └── app.py             # Streamlit (placeholder — Fase 4)
├── tests/                      # 12 arquivos de teste, 76 testes
├── scripts/
│   ├── download_srag_data.py  # Download CSVs do DATASUS S3
│   ├── seed_db.py             # Carga no PostgreSQL
│   ├── validate_data.py       # Sanity checks
│   ├── explore_data.py        # Exploração de dados
│   ├── test_llm.py            # Validação de conectividade LLM
│   └── run_agent.py           # CLI runner do agente
└── docs/
    ├── data_privacy.md         # Decisões PII/LGPD
    └── ideas/                  # Planos de implementação
```

## Melhorias Futuras

Itens planejados para implementação posterior (detalhes em `docs/ideas/improvements_plan.md`):

| Prioridade | Item | Descrição |
|-----------|------|-----------|
| Alta | Cache de buscas | Evitar buscar notícias repetidas em execuções seguidas |
| Alta | Fallback Tavily | Busca de notícias quando DuckDuckGo falha |
| Alta | Validação cruzada | Comparar métricas com painéis do Ministério da Saúde |
| Média | UI Streamlit | Interface web com métricas, gráficos, relatório e audit |
| Média | Multi-agente | Arquitetura com especialistas (epidemiologista, vacinólogo) |
| Média | Embeddings multilingual | Avaliar BAAI/bge-m3 para melhor busca em PT-BR |
| Baixa | Download automático | Agendamento de atualização dos dados SRAG |
| Baixa | PDF customizado | Melhor layout com tabelas e gráficos embutidos |

## Licença

Projeto acadêmico para certificação de AI Engineer. Dados públicos do DATASUS (Portaria GM/MS No. 1.119/2022).