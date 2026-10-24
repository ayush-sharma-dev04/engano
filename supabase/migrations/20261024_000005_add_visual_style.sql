BEGIN;

-- The brand's look: fonts and hex colours a website or design should stay within.
ALTER TABLE public.brand_policies
    ADD COLUMN IF NOT EXISTS visual_style JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMIT;
