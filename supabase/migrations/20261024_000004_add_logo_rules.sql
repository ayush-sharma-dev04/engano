BEGIN;

-- What a brand expects to see (and not see) in images: require_brand_logo, approved_partners.
ALTER TABLE public.brand_policies
    ADD COLUMN IF NOT EXISTS logo_rules JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMIT;
