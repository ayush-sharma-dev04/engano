BEGIN;

CREATE TABLE IF NOT EXISTS public.reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id TEXT NOT NULL,
    brand_id TEXT NOT NULL,
    completion_status TEXT NOT NULL DEFAULT 'completed',
    decision_status TEXT NOT NULL,
    decision_action_required_by TEXT,
    decision_clarification_question TEXT,
    decision_reason TEXT,
    findings JSONB NOT NULL DEFAULT '[]'::jsonb,
    proposed_rewrite TEXT,
    original_text TEXT,
    rewrite_proposal JSONB,
    post_rewrite_findings JSONB NOT NULL DEFAULT '[]'::jsonb,
    post_rewrite_decision JSONB,
    provider_selected TEXT,
    agents_executed JSONB NOT NULL DEFAULT '[]'::jsonb,
    processing_time_ms DOUBLE PRECISION,
    fallback_occurred BOOLEAN NOT NULL DEFAULT FALSE,
    fallback_details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "reviews_allow_anon_and_authenticated_access"
    ON public.reviews;

REVOKE ALL PRIVILEGES ON TABLE public.reviews
    FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA public TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.reviews
    TO service_role;

COMMIT;
