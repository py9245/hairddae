ALTER TABLE users
    ADD COLUMN IF NOT EXISTS provider_subject VARCHAR(255);

ALTER TABLE users
    DROP CONSTRAINT IF EXISTS uq_users_provider_subject;

ALTER TABLE users
    ADD CONSTRAINT uq_users_provider_subject UNIQUE (provider_subject);
