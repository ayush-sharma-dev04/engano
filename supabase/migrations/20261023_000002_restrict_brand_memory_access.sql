BEGIN;

ALTER TABLE public.brand_memory ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "brand_memory_allow_anon_and_authenticated_access"
    ON public.brand_memory;

REVOKE ALL PRIVILEGES ON TABLE public.brand_memory
    FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA public TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.brand_memory
    TO service_role;

COMMIT;
