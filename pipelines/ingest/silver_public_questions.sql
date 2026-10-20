-- Public questions, cleaned and deduplicated, with a deterministic rank: every Bitext (banking)
-- row ranks ahead of GooAQ, so a load-test cache of N entries is always "the first N rows" and
-- the in-domain near-misses are present at every size.
CREATE OR REFRESH MATERIALIZED VIEW silver_public_questions (
  CONSTRAINT reasonable_length EXPECT (length(question) BETWEEN 5 AND 300) ON VIOLATION DROP ROW,
  CONSTRAINT has_answer EXPECT (answer IS NOT NULL)
)
COMMENT "Public banking (Bitext) and search (GooAQ) questions, trimmed, deduplicated case-insensitively and ranked. Load-test distractors for the cache."
AS
WITH src AS (
  SELECT 'bitext' AS source, 0 AS source_order, trim(instruction) AS question,
         left(response, 500) AS answer, intent AS source_label
  FROM bronze_bitext
  UNION ALL
  SELECT 'gooaq', 1, trim(question), left(answer, 500), CAST(NULL AS STRING)
  FROM bronze_gooaq
),
dedup AS (
  SELECT * FROM src
  WHERE question IS NOT NULL
  QUALIFY row_number() OVER (PARTITION BY lower(question) ORDER BY source_order) = 1
)
SELECT row_number() OVER (ORDER BY source_order, xxhash64(question)) - 1 AS rank,
       source, question, answer, source_label
FROM dedup;
