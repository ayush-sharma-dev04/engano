BEGIN;

CREATE TABLE IF NOT EXISTS public.brand_policies (
    brand_id TEXT PRIMARY KEY
        CHECK (brand_id ~ '^[a-z0-9_-]+$'),
    brand_name TEXT NOT NULL,
    description TEXT,
    approved_terminology JSONB NOT NULL DEFAULT '[]'::jsonb,
    claims_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    factual_rules JSONB NOT NULL DEFAULT '[]'::jsonb,
    offers JSONB NOT NULL DEFAULT '[]'::jsonb,
    tone_rules JSONB NOT NULL DEFAULT '[]'::jsonb,
    accessibility_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    legal_rules JSONB NOT NULL DEFAULT '[]'::jsonb,
    test_fixtures JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1)
);

ALTER TABLE public.brand_policies ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "brand_policies_allow_anon_and_authenticated_access"
    ON public.brand_policies;

REVOKE ALL PRIVILEGES ON TABLE public.brand_policies
    FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA public TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.brand_policies
    TO service_role;

COMMIT;
