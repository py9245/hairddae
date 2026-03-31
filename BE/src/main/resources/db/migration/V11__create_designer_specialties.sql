CREATE TABLE IF NOT EXISTS designer_specialties (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    category_id VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_designer_specialties_user
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_designer_specialties_category
        FOREIGN KEY (category_id) REFERENCES hair_categories (category_id) ON DELETE RESTRICT,
    CONSTRAINT uq_designer_specialties_user_category UNIQUE (user_id, category_id)
);

CREATE INDEX IF NOT EXISTS idx_designer_specialties_user_id
    ON designer_specialties (user_id, created_at ASC);
