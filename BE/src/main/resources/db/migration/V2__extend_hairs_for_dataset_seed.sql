ALTER TABLE hairs
    ADD COLUMN IF NOT EXISTS slug VARCHAR(120),
    ADD COLUMN IF NOT EXISTS dataset_code VARCHAR(50),
    ADD COLUMN IF NOT EXISTS dataset_root_url VARCHAR(500),
    ADD COLUMN IF NOT EXISTS asset_index_url VARCHAR(500),
    ADD COLUMN IF NOT EXISTS representative_asset_id VARCHAR(255);

CREATE UNIQUE INDEX IF NOT EXISTS uq_hairs_slug
    ON hairs (slug)
    WHERE slug IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_hairs_dataset_code
    ON hairs (dataset_code)
    WHERE dataset_code IS NOT NULL;
