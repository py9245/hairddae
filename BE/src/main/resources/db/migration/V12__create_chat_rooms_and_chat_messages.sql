CREATE TABLE IF NOT EXISTS chat_rooms (
    id BIGSERIAL PRIMARY KEY,
    customer_user_id VARCHAR(50) NOT NULL,
    designer_user_id VARCHAR(50) NOT NULL,
    source_hair_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_chat_rooms_customer_designer UNIQUE (customer_user_id, designer_user_id),
    CONSTRAINT fk_chat_rooms_customer
        FOREIGN KEY (customer_user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_rooms_designer
        FOREIGN KEY (designer_user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_rooms_source_hair
        FOREIGN KEY (source_hair_id) REFERENCES hairs (id) ON DELETE SET NULL,
    CONSTRAINT chk_chat_rooms_customer_designer_distinct CHECK (customer_user_id <> designer_user_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_rooms_customer_user_id
    ON chat_rooms (customer_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chat_rooms_designer_user_id
    ON chat_rooms (designer_user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGSERIAL PRIMARY KEY,
    room_id BIGINT NOT NULL,
    sender_user_id VARCHAR(50) NOT NULL,
    message_type VARCHAR(20) NOT NULL,
    message_text TEXT,
    image_url VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMPTZ,
    CONSTRAINT fk_chat_messages_room
        FOREIGN KEY (room_id) REFERENCES chat_rooms (id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_messages_sender
        FOREIGN KEY (sender_user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    CONSTRAINT chk_chat_messages_type CHECK (message_type IN ('TEXT', 'IMAGE')),
    CONSTRAINT chk_chat_messages_payload CHECK (
        (message_type = 'TEXT' AND message_text IS NOT NULL AND image_url IS NULL)
        OR
        (message_type = 'IMAGE' AND image_url IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_room_id_id
    ON chat_messages (room_id, id ASC);
