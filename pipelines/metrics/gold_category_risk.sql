-- Which kinds of question are risky to cache: per FAQ category and threshold, from the latest
-- 02_evaluate lookups. Money-movement categories are flagged so they can be held to a higher bar.
CREATE OR REFRESH MATERIALIZED VIEW gold_category_risk
COMMENT "Cache accuracy by FAQ category and similarity threshold (latest 02_evaluate run). caught_rate: paraphrases served the right FAQ; wrong_rate_cached: paraphrases served another FAQ's answer; wrong_rate_uncached: paraphrases that would get a wrong answer if their own FAQ were not cached (leave-one-FAQ-out). money_movement flags payments, withdrawals, deposits, funding, limits and disputes."
AS
WITH latest AS (
  SELECT * FROM ${catalog}.${schema}.eval_lookups
  QUALIFY run_ts = max(run_ts) OVER (PARTITION BY backend)
),
pct AS (SELECT explode(sequence(60, 90, 5)) AS p),
t AS (SELECT p / 100.0 AS threshold FROM pct)
SELECT l.backend, coalesce(f.category, 'account_specific') AS category, coalesce(f.money_movement, false) AS money_movement,
       t.threshold,
       count(*) AS questions,
       count_if(l.similarity >= t.threshold AND l.match_correct) / count(*) AS caught_rate,
       count_if(l.similarity >= t.threshold AND NOT l.match_correct) / count(*) AS wrong_rate_cached,
       count_if(l.novel_similarity >= t.threshold) / count(*) AS wrong_rate_uncached,
       max(l.run_ts) AS run_ts
FROM latest l
LEFT JOIN ${catalog}.${schema}.silver_faq_intents f ON f.intent_id = l.expected_intent
CROSS JOIN t
GROUP BY ALL;
