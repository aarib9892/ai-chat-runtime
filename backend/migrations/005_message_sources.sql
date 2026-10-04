CREATE TABLE message_sources (
    message_id UUID NOT NULL
        REFERENCES messages(id)
        ON DELETE CASCADE,

    chunk_id UUID NOT NULL
        REFERENCES document_chunks(id)
        ON DELETE CASCADE,

    rank INTEGER NOT NULL
        CHECK (rank > 0),

    similarity DOUBLE PRECISION NOT NULL,

    PRIMARY KEY (message_id, chunk_id),
    UNIQUE (message_id, rank)
);


CREATE INDEX idx_message_sources_message_rank
ON message_sources (message_id, rank);
