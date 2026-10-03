CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE document_chunks
ADD COLUMN embedding vector(1536);


ALTER TABLE document_chunks
ADD COLUMN embedding_model TEXT;

ALTER TABLE document_chunks
ADD COLUMN embedded_at TIMESTAMPTZ;


CREATE INDEX idx_document_chunks_embedding_cosine
ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WHERE embedding IS NOT NULL;
