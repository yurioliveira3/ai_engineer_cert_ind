-- 05_news.sql
-- News embeddings table and vector index

CREATE TABLE IF NOT EXISTS news.news_embeddings (
    id          SERIAL PRIMARY KEY,
    url         TEXT UNIQUE NOT NULL,
    title       TEXT,
    snippet     TEXT,
    source      TEXT,
    query_used  TEXT,
    embedding   vector(1024),
    indexed_at  TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index for approximate nearest neighbor search.
-- Unlike IVFFlat, HNSW builds progressively as rows are inserted, so it works
-- correctly even when created on an empty table (IVFFlat has no centroids without data).
CREATE INDEX IF NOT EXISTS news_embeddings_vec_idx
    ON news.news_embeddings
    USING hnsw (embedding vector_cosine_ops);

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA news TO srag_app;
GRANT USAGE ON SCHEMA news TO srag_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA news GRANT SELECT, INSERT, UPDATE ON TABLES TO srag_app;