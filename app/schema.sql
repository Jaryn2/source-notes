CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS sessions (
 token_hash text PRIMARY KEY, csrf text NOT NULL, expires_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
 id uuid PRIMARY KEY, title text NOT NULL, body text NOT NULL, digest text NOT NULL UNIQUE,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS chunks (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, document_id uuid NOT NULL REFERENCES documents(id),
 passage text NOT NULL, start_line integer NOT NULL, end_line integer NOT NULL,
 embedding vector(256) NOT NULL, flagged boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id);
CREATE TABLE IF NOT EXISTS answers (
 id uuid PRIMARY KEY, request_key uuid NOT NULL UNIQUE, question text NOT NULL, mode text NOT NULL,
 status text NOT NULL, answer text NOT NULL, citations jsonb NOT NULL,
 duration_ms integer NOT NULL, input_tokens integer NOT NULL DEFAULT 0, output_tokens integer NOT NULL DEFAULT 0,
 estimated_cost numeric, error text, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS notes (
 id uuid PRIMARY KEY, answer_id uuid NOT NULL UNIQUE REFERENCES answers(id),
 title text NOT NULL, status text NOT NULL DEFAULT 'pending',
 reviewed_by text, reviewed_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS evaluations (
 id uuid PRIMARY KEY, mode text NOT NULL, cases jsonb NOT NULL, passed integer NOT NULL,
 total integer NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
