BEGIN;

CREATE TABLE IF NOT EXISTS public.brand_memory (
    brand_id TEXT PRIMARY KEY
        CHECK (brand_id ~ '^[a-z0-9_-]+$'),
    brand_name TEXT NOT NULL,
    description TEXT,
    voice_and_tone_preferences JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (
            jsonb_typeof(voice_and_tone_preferences) = 'array'
            AND NOT jsonb_path_exists(
                voice_and_tone_preferences,
                '$[*] ? (@.type() != "string")'
            )
        ),
    target_audience TEXT,
    approved_terminology JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (
            jsonb_typeof(approved_terminology) = 'array'
            AND NOT jsonb_path_exists(
                approved_terminology,
                '$[*] ? (@.type() != "string")'
            )
        ),
    verified_facts JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (
            jsonb_typeof(verified_facts) = 'array'
            AND NOT jsonb_path_exists(
                verified_facts,
                '$[*] ? (@.type() != "string")'
            )
        ),
    custom_preferences JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(custom_preferences) = 'object'),
    policy_reference TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1)
);

ALTER TABLE public.brand_memory ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "brand_memory_allow_anon_and_authenticated_access"
    ON public.brand_memory;

REVOKE ALL PRIVILEGES ON TABLE public.brand_memory
    FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA public TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.brand_memory
    TO service_role;

COMMIT;
