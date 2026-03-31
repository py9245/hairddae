INSERT INTO hair_categories (
    category_id,
    category_name,
    display_order,
    is_active,
    created_at,
    updated_at
)
SELECT DISTINCT
    BTRIM(category) AS category_id,
    BTRIM(category) AS category_name,
    0,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM hairs
WHERE category IS NOT NULL
  AND BTRIM(category) <> ''
ON CONFLICT (category_id) DO NOTHING;

ALTER TABLE hairs
    ADD COLUMN IF NOT EXISTS category_id VARCHAR(50);

UPDATE hairs
SET category_id = BTRIM(category)
WHERE category_id IS NULL
  AND category IS NOT NULL
  AND BTRIM(category) <> '';

CREATE INDEX IF NOT EXISTS idx_hairs_category_id_active
    ON hairs (category_id, is_active);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_hairs_category_id'
    ) THEN
        ALTER TABLE hairs
            ADD CONSTRAINT fk_hairs_category_id
            FOREIGN KEY (category_id)
            REFERENCES hair_categories (category_id)
            ON DELETE RESTRICT;
    END IF;
END $$;
