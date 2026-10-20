-- Embedded load-test distractors: the first ${scale_rows} ranked questions become cache entries, and
-- the last ${holdout_rows} (GooAQ, never loaded) are held-out "miss" traffic for 03b_load_test.
CREATE OR REFRESH MATERIALIZED VIEW gold_scale_embeddings (
  CONSTRAINT embedded EXPECT (embedding IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT dimension EXPECT (size(embedding) = 1024)
)
COMMENT "Public questions embedded with ai_query() on the cache's embedding endpoint. holdout = true rows are never loaded into the cache."
AS
WITH bounds AS (SELECT max(rank) + 1 AS total FROM silver_public_questions),
picked AS (
  SELECT q.*, q.rank >= b.total - ${holdout_rows} AS holdout
  FROM silver_public_questions q CROSS JOIN bounds b
  WHERE q.rank < ${scale_rows} OR q.rank >= b.total - ${holdout_rows}
)
SELECT rank, source, question, answer, source_label, holdout,
       CAST(ai_query('${embedding_endpoint}', question) AS ARRAY<FLOAT>) AS embedding
FROM picked;
