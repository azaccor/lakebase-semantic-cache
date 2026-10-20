-- The labeled evaluation set: held-out paraphrases of each FAQ, plus the account-specific probes.
CREATE OR REFRESH MATERIALIZED VIEW silver_eval_questions (
  CONSTRAINT question_present EXPECT (length(trim(question)) > 0) ON VIOLATION DROP ROW,
  CONSTRAINT label_consistent EXPECT (cacheable = (expected_intent IS NOT NULL))
)
COMMENT "Labeled evaluation questions. Cacheable rows are paraphrases of a cached FAQ (expected_intent is the right answer); account-specific rows are probes the cache must never answer. Used by 02_evaluate and the app's replay."
AS
SELECT
  trim(p.question) AS question,
  CASE WHEN f.cacheable THEN f.intent_id END AS expected_intent,
  f.intent_id AS source_intent,
  f.category,
  f.money_movement,
  f.cacheable,
  CASE WHEN f.cacheable THEN 'paraphrase' ELSE 'account_specific_probe' END AS kind
FROM silver_faq_intents f
JOIN (
  SELECT i.intent_id, q AS question
  FROM (SELECT * FROM bronze_question_bank
        QUALIFY row_number() OVER (ORDER BY file_modified_at DESC, ingested_at DESC) = 1)
  LATERAL VIEW explode(intents) AS i
  LATERAL VIEW explode(
    CASE WHEN i.cacheable THEN i.paraphrases ELSE concat(array(i.canonical_question), i.paraphrases) END) AS q
) p ON p.intent_id = f.intent_id;
