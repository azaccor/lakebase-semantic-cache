-- Daily cache KPIs from the request log: deflection (share answered without an LLM call), latency,
-- and LLM cost per question with and without the cache. One LLM call is priced from the calls that
-- actually ran in the same prompt version (the system prompt sets the input tokens), at list price.
CREATE OR REFRESH MATERIALIZED VIEW gold_cache_daily
COMMENT "Daily semantic-cache KPIs by traffic type, FAQ category and prompt version (is_current_prompt marks the system prompt in use now): requests, deflection (hit) rate, latency, and modeled LLM cost per question with vs without the cache. traffic_type: live = Playground questions, replay = labeled evaluation traffic replayed through the app, seed = 01_build_cache."
AS
WITH ev AS (
  SELECT
    date(e.event_ts) AS event_date,
    CASE e.source WHEN 'app' THEN 'live' WHEN 'app-replay' THEN 'replay' WHEN '01_build_cache' THEN 'seed' ELSE e.source END AS traffic_type,
    e.scope['model'] AS model,
    e.scope['prompt_version'] AS prompt_version,
    e.backend, e.hit, e.threshold, e.similarity, e.total_ms, e.input_tokens, e.output_tokens, e.generate_ms,
    get_json_object(e.matched_metadata, '$.intent_id') AS matched_intent,
    coalesce(get_json_object(e.attributes, '$.expected_intent'), get_json_object(e.attributes, '$.intent_id')) AS question_intent,
    get_json_object(e.attributes, '$.cacheable') AS cacheable_label
  FROM ${catalog}.${schema}.cache_events e
),
-- The system prompt in use now: the one on the most recent request for each model.
current_prompt AS (
  SELECT scope['model'] AS model, max_by(scope['prompt_version'], event_ts) AS prompt_version
  FROM ${catalog}.${schema}.cache_events GROUP BY 1
),
call_cost AS (
  SELECT model, prompt_version,
         (avg(input_tokens) * ${price_in_per_m} + avg(output_tokens) * ${price_out_per_m}) / 1e6 AS llm_cost_per_call,
         avg(generate_ms) AS llm_ms_per_call
  FROM ev WHERE NOT hit AND input_tokens > 0
  GROUP BY ALL
),
labeled AS (
  SELECT ev.*,
         coalesce(qi.category, CASE WHEN ev.hit THEN mi.category END, 'unlabeled') AS category,
         coalesce(qi.money_movement, CASE WHEN ev.hit THEN mi.money_movement END) AS money_movement,
         -- Replayed questions carry their true FAQ, so a hit on the wrong FAQ (or on an account-specific probe) is known to be wrong.
         CASE WHEN ev.cacheable_label IS NULL OR NOT ev.hit THEN NULL
              WHEN ev.cacheable_label = 'false' THEN true
              ELSE ev.matched_intent IS DISTINCT FROM ev.question_intent END AS wrong_hit
  FROM ev
  LEFT JOIN ${catalog}.${schema}.silver_faq_intents qi ON qi.intent_id = ev.question_intent
  LEFT JOIN ${catalog}.${schema}.silver_faq_intents mi ON mi.intent_id = ev.matched_intent
)
SELECT
  l.event_date, l.traffic_type, l.category, l.money_movement, l.model, l.prompt_version,
  l.prompt_version = cp.prompt_version AS is_current_prompt, l.backend,
  round(avg(l.threshold), 2) AS threshold,
  count(*) AS requests,
  count_if(l.hit) AS hits,
  count_if(l.hit) / count(*) AS deflection_rate,
  count(l.wrong_hit) AS labeled_hits,
  count_if(l.wrong_hit) AS labeled_wrong_hits,
  avg(l.total_ms) AS avg_latency_ms,
  avg(CASE WHEN l.hit THEN l.total_ms END) AS avg_hit_latency_ms,
  max(c.llm_ms_per_call) AS llm_latency_ms,
  max(c.llm_cost_per_call) AS baseline_cost_per_question_usd,
  max(c.llm_cost_per_call) * (1 - count_if(l.hit) / count(*)) + ${embed_cost_per_question} AS cost_per_question_usd,
  count(*) * max(c.llm_cost_per_call) AS baseline_llm_cost_usd,
  count_if(NOT l.hit) * max(c.llm_cost_per_call) + count(*) * ${embed_cost_per_question} AS llm_cost_usd,
  count_if(l.hit) * max(c.llm_cost_per_call) - count(*) * ${embed_cost_per_question} AS savings_usd
FROM labeled l
LEFT JOIN call_cost c ON c.model = l.model AND c.prompt_version = l.prompt_version
LEFT JOIN current_prompt cp ON cp.model = l.model
GROUP BY ALL;
