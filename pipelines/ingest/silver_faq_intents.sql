-- One row per support FAQ (intent), from the latest question bank file.
CREATE OR REFRESH MATERIALIZED VIEW silver_faq_intents (
  CONSTRAINT intent_id_present EXPECT (intent_id IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT question_present EXPECT (length(trim(canonical_question)) > 0) ON VIOLATION DROP ROW,
  CONSTRAINT cacheable_has_reference EXPECT (NOT cacheable OR length(reference_answer) > 0),
  CONSTRAINT cacheable_has_paraphrases EXPECT (NOT cacheable OR n_paraphrases >= 2)
)
COMMENT "Lux Pay support FAQs: one row per intent with its category, money-movement flag and whether it may be cached. Account-specific intents (cacheable = false) must never be served from the cache."
AS
WITH latest AS (
  SELECT * FROM bronze_question_bank
  QUALIFY row_number() OVER (ORDER BY file_modified_at DESC, ingested_at DESC) = 1
)
SELECT
  i.intent_id,
  i.category,
  i.category IN ('payments', 'withdrawals', 'deposits', 'funding', 'limits', 'disputes') AS money_movement,
  trim(i.canonical_question) AS canonical_question,
  i.reference_answer,
  i.cacheable,
  i.non_cacheable_reason,
  size(i.paraphrases) AS n_paraphrases,
  latest.source_file
FROM latest LATERAL VIEW explode(intents) AS i;
