-- Raw question bank files, one row per file version, as landed by notebooks/00a_land_raw.
CREATE OR REFRESH STREAMING TABLE bronze_question_bank
COMMENT "Raw synthetic Lux Pay question bank: support FAQs with labeled paraphrases and account-specific probes. One row per file version."
AS SELECT
  persona,
  notes,
  intents,
  _metadata.file_path AS source_file,
  _metadata.file_modification_time AS file_modified_at,
  current_timestamp() AS ingested_at
FROM STREAM read_files(
  '${raw_path}/question_bank/',
  format => 'json',
  multiLine => true,
  schema => 'persona STRING, notes STRING, intents ARRAY<STRUCT<intent_id: STRING, category: STRING, canonical_question: STRING, paraphrases: ARRAY<STRING>, reference_answer: STRING, cacheable: BOOLEAN, non_cacheable_reason: STRING>>'
);
