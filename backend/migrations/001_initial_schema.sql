CREATE EXTENSION IF NOT EXISTS pgcrypto;


CREATE TABLE conversations(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);

CREATE TABLE MESSAGES(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL
        REFERENCES conversations(id)
        ON DELETE CASCADE,

    role TEXT NOT NULL
        CHECK (role IN ('user' , 'assistant')),

    content TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'completed'
        Check (
            status IN (
                'streaming',
                'completed',
                'stopped',
                'error'
            )
        ),
    
    provider_response_id TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);

CREATE INDEX idx_messages_conversation_created ON messages (conversation_id,created_at);
-- 59bcf538-5dae-4ce5-8227-0230c5f84337
-- INSERT INTO messages (
--     conversation_id,
--     role,
--     content
-- )
-- VALUES (
--     '59bcf538-5dae-4ce5-8227-0230c5f84337',
--     'user',
--     'Hi, my name is Raj'
-- )
-- RETURNING *;

-- INSERT INTO messages (
--     conversation_id,
--     role,
--     content
-- )
-- VALUES (
--     '59bcf538-5dae-4ce5-8227-0230c5f84337',
--     'assistant',
--     'Hi Raj! Nice to meet you.'
-- );

-- INSERT INTO messages (
--     conversation_id,
--     role,
--     content
-- )
-- VALUES (
--     '59bcf538-5dae-4ce5-8227-0230c5f84337',
--     'user',
--     'What is my name?'
-- );