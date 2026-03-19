ALTER TABLE users
    ADD COLUMN IF NOT EXISTS birth_date DATE;

UPDATE users
SET birth_date = (CURRENT_DATE - make_interval(years => age))::date
WHERE age IS NOT NULL
  AND birth_date IS NULL;

ALTER TABLE users
    DROP CONSTRAINT IF EXISTS chk_users_age;

ALTER TABLE users
    DROP COLUMN IF EXISTS age;

ALTER TABLE users
    ADD CONSTRAINT chk_users_birth_date CHECK (birth_date IS NULL OR birth_date >= DATE '1900-01-01');
