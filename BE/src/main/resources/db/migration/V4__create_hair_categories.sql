CREATE TABLE IF NOT EXISTS hair_categories (
    id BIGSERIAL PRIMARY KEY,
    category_id VARCHAR(50) NOT NULL,
    category_name VARCHAR(120) NOT NULL,
    preview_image_url VARCHAR(500),
    description TEXT,
    display_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_hair_categories_category_id UNIQUE (category_id)
);

CREATE INDEX IF NOT EXISTS idx_hair_categories_active_order
    ON hair_categories (is_active, display_order ASC, created_at ASC);
