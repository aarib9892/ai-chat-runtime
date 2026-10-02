CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    filename TEXT NOT NULL,

    mime_type TEXT,

    content TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    document_id UUID NOT NULL
        REFERENCES documents(id)
        ON DELETE CASCADE,

    chunk_index INTEGER NOT NULL,

    content TEXT NOT NULL,

    token_count INTEGER NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(document_id, chunk_index)
);


CREATE INDEX idx_document_chunks_document
ON document_chunks (
    document_id,
    chunk_index
);
