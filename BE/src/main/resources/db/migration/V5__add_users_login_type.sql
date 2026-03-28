ALTER TABLE users
    ADD COLUMN IF NOT EXISTS login_type SMALLINT;

UPDATE users
SET login_type = 0
WHERE login_type IS NULL;

ALTER TABLE users
    ALTER COLUMN login_type SET DEFAULT 0;

ALTER TABLE users
    ALTER COLUMN login_type SET NOT NULL;

ALTER TABLE users
    DROP CONSTRAINT IF EXISTS chk_users_login_type;

ALTER TABLE users
    ADD CONSTRAINT chk_users_login_type CHECK (login_type IN (0, 1));
