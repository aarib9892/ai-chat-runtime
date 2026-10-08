ALTER TABLE message_tool_calls
ADD COLUMN step_number INTEGER
    CHECK (step_number IS NULL OR step_number > 0);

CREATE INDEX idx_message_tool_calls_message_step
ON message_tool_calls(message_id, step_number);

CREATE TABLE message_agent_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    message_id UUID NOT NULL
        REFERENCES messages(id)
        ON DELETE CASCADE,

    step_number INTEGER NOT NULL
        CHECK (step_number > 0),

    provider_response_id TEXT,

    status TEXT NOT NULL DEFAULT 'running'
        CHECK (
            status IN (
                'running',
                'completed',
                'incomplete',
                'stopped',
                'error'
            )
        ),

    outcome TEXT
        CHECK (
            outcome IS NULL
            OR outcome IN (
                'tool',
                'final',
                'continue'
            )
        ),

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    UNIQUE(message_id, step_number)
);

CREATE INDEX idx_message_agent_steps_message_step
ON message_agent_steps(message_id, step_number);
