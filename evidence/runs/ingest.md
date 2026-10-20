# Task `ingest` (job run 32232528631469)

Result: **SUCCESS**, 2026-10-20 00:59:49 UTC – 2026-10-20 01:01:12 UTC.

Pipeline `semantic_cache_ingest`, update `2666f85f-ef30-44a9-aaf6-8806daec3ed4`: **COMPLETED**

Streaming (bronze) tables only read new files, so a re-run writes 0 rows to them; materialized views recompute.

| dataset | rows written this update | rows in table | rows dropped |
|---|---|---|---|
| bronze_bitext | 0 (no new input) | 25545 |  |
| bronze_gooaq | 0 (no new input) | 3012496 |  |
| bronze_question_bank | 0 (no new input) | 1 |  |
| gold_scale_embeddings | 102000 | 102000 | 0 |
| silver_eval_questions | 175 | 175 | 0 |
| silver_faq_intents | 52 | 52 | 0 |
| silver_public_questions | 3037931 | 3037931 | 0 |

Data-quality expectations:

| dataset | expectation | passed | failed |
|---|---|---|---|
| gold_scale_embeddings | embedded | 102000 | 0 |
| gold_scale_embeddings | dimension | 102000 | 0 |
| silver_eval_questions | question_present | 175 | 0 |
| silver_eval_questions | label_consistent | 175 | 0 |
| silver_faq_intents | intent_id_present | 52 | 0 |
| silver_faq_intents | question_present | 52 | 0 |
| silver_faq_intents | cacheable_has_paraphrases | 52 | 0 |
| silver_faq_intents | cacheable_has_reference | 52 | 0 |
| silver_public_questions | reasonable_length | 3037931 | 0 |
| silver_public_questions | has_answer | 3037931 | 0 |
