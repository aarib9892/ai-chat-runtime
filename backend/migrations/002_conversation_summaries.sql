ALTER TABLE messages
    DROP CONSTRAINT IF EXISTS messages_status_check;

ALTER TABLE messages
    ADD CONSTRAINT messages_status_check CHECK (
        status IN ('streaming', 'completed', 'stopped', 'error', 'incomplete')
    );

CREATE TABLE conversation_summaries(
    conversation_id UUID PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    through_message_id UUID NOT NULL REFERENCES messages(id),
    token_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);
