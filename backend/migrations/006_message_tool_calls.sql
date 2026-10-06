CREATE TABLE message_tool_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    message_id UUID NOT NULL
        REFERENCES messages(id)
        ON DELETE CASCADE,

    call_id TEXT NOT NULL,

    tool_name TEXT NOT NULL,

    arguments JSONB NOT NULL,

    result JSONB,

    status TEXT NOT NULL DEFAULT 'running'
        CHECK (
            status IN (
                'running',
                'completed',
                'error'
            )
        ),

    error TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    completed_at TIMESTAMPTZ,

    UNIQUE(message_id, call_id)
);

CREATE INDEX idx_message_tool_calls_message_created
ON message_tool_calls(message_id, created_at);