ALTER TABLE message_agent_steps
ADD COLUMN duration_ms DOUBLE PRECISION
    CHECK (duration_ms IS NULL OR duration_ms >= 0),
ADD COLUMN input_tokens INTEGER
    CHECK (input_tokens IS NULL OR input_tokens >= 0),
ADD COLUMN output_tokens INTEGER
    CHECK (output_tokens IS NULL OR output_tokens >= 0),
ADD COLUMN total_tokens INTEGER
    CHECK (total_tokens IS NULL OR total_tokens >= 0);

CREATE TABLE message_usage (
    message_id UUID PRIMARY KEY
        REFERENCES messages(id)
        ON DELETE CASCADE,

    model TEXT NOT NULL,

    model_calls INTEGER NOT NULL
        CHECK (model_calls > 0),

    input_tokens INTEGER NOT NULL
        CHECK (input_tokens >= 0),

    output_tokens INTEGER NOT NULL
        CHECK (output_tokens >= 0),

    total_tokens INTEGER NOT NULL
        CHECK (total_tokens >= 0),

    duration_ms DOUBLE PRECISION NOT NULL
        CHECK (duration_ms >= 0),

    estimated_cost_usd DOUBLE PRECISION NOT NULL
        CHECK (estimated_cost_usd >= 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_one_streaming_assistant_per_conversation
ON messages(conversation_id)
WHERE role = 'assistant' AND status = 'streaming';
