-- Enable pg_trgm so PostgreSQL can index substring/ILIKE patterns.
-- A B-tree index cannot accelerate ILIKE '%keyword%' (leading wildcard),
-- but a GIN trigram index breaks text into character 3-grams and CAN.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- GIN trigram index on title — primary field for keyword filtering
CREATE INDEX IF NOT EXISTS bills_title_trgm_idx ON bills USING GIN (title gin_trgm_ops);

-- GIN trigram index on description — secondary field (often sparse from LegiScan stubs)
CREATE INDEX IF NOT EXISTS bills_desc_trgm_idx ON bills USING GIN (description gin_trgm_ops);
