-- The cost-versus-accuracy dial from the latest 02_evaluate run, per backend.
CREATE OR REFRESH MATERIALIZED VIEW gold_threshold_curve
COMMENT "Hit and wrong-answer rates by similarity threshold from the latest 02_evaluate run. repeat_caught_rate: share of repeat questions served from cache; wrong_rate_repeat: share of repeat questions given another FAQ's answer; wrong_rate_uncached: share of questions the cache does not hold that still get a (wrong) cached answer (leave-one-FAQ-out). The *_at_50pct_repeat columns combine them for traffic where half the questions repeat a cached FAQ."
AS
SELECT s.backend, s.threshold,
       s.cacheable_hit_rate AS repeat_caught_rate,
       s.cacheable_false_hit_rate AS wrong_rate_repeat,
       s.novel_hit_rate AS wrong_rate_uncached,
       0.5 * s.cacheable_hit_rate + 0.5 * s.novel_hit_rate AS hit_rate_at_50pct_repeat,
       0.5 * s.cacheable_false_hit_rate + 0.5 * s.novel_hit_rate AS wrong_per_request_at_50pct_repeat,
       s.account_specific_hits,
       s.run_id, s.run_ts
FROM ${catalog}.${schema}.eval_threshold_sweep s
WHERE s.cacheable_false_hit_rate IS NOT NULL
QUALIFY s.run_ts = max(s.run_ts) OVER (PARTITION BY s.backend);
