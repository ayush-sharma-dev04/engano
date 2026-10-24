BEGIN;

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

CREATE TABLE IF NOT EXISTS public.brand_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id TEXT NOT NULL
        CHECK (brand_id ~ '^[a-z0-9_-]+$'),
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding extensions.vector(768) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (brand_id, source, source_id)
);

CREATE INDEX IF NOT EXISTS brand_chunks_embedding_idx
    ON public.brand_chunks
    USING hnsw (embedding extensions.vector_cosine_ops);

ALTER TABLE public.brand_chunks ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON TABLE public.brand_chunks
    FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA public TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.brand_chunks
    TO service_role;

-- Nearest chunks for one brand. Brand isolation is enforced in the WHERE clause.
CREATE OR REPLACE FUNCTION public.match_brand_chunks(
    p_brand_id TEXT,
    p_query_embedding extensions.vector(768),
    p_match_count INTEGER DEFAULT 6
)
RETURNS TABLE (
    source TEXT,
    source_id TEXT,
    content TEXT,
    metadata JSONB,
    similarity DOUBLE PRECISION
)
LANGUAGE sql
STABLE
SET search_path = public, extensions
AS $$
    SELECT c.source, c.source_id, c.content, c.metadata,
           1 - (c.embedding <=> p_query_embedding) AS similarity
    FROM public.brand_chunks c
    WHERE c.brand_id = p_brand_id
    ORDER BY c.embedding <=> p_query_embedding
    LIMIT LEAST(GREATEST(p_match_count, 1), 20);
$$;

REVOKE ALL ON FUNCTION public.match_brand_chunks(TEXT, extensions.vector, INTEGER)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.match_brand_chunks(TEXT, extensions.vector, INTEGER)
    TO service_role;

COMMIT;
