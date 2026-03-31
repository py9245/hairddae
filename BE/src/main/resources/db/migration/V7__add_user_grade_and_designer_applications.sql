ALTER TABLE users
    ADD COLUMN IF NOT EXISTS grade SMALLINT NOT NULL DEFAULT 0;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_users_grade'
    ) THEN
        ALTER TABLE users
            ADD CONSTRAINT chk_users_grade CHECK (grade IN (0, 1, 2));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS designer_applications (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    certificate_number VARCHAR(255) NOT NULL,
    salon_address VARCHAR(500) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_designer_applications_user_id UNIQUE (user_id),
    CONSTRAINT fk_designer_applications_user_id
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);
