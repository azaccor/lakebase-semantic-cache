-- Drift monitor: the judged false-hit rate over the last ${monitor_window_days} days, per cache prompt
-- version, against a limit. ALERT when even the low end of the 95% interval is above the limit.
CREATE OR REFRESH MATERIALIZED VIEW gold_false_hit_monitor
COMMENT "False-hit drift monitor per cache prompt version over a trailing window: judged false-hit rate, Wilson 95% interval, the configured limit, and a status (OK, WATCH = point estimate above the limit, ALERT = whole interval above it, INSUFFICIENT_DATA)."
AS
WITH w AS (
  SELECT prompt_version, judge_version, judge_model,
         count(*) AS judged, count_if(verdict = 'incorrect') AS judged_incorrect,
         round(avg(threshold), 2) AS threshold_in_use,
         min(judged_ts) AS window_start, max(judged_ts) AS last_judged_ts
  FROM ${catalog}.${schema}.judge_results
  WHERE verdict IN ('correct', 'incorrect') AND prompt_version IS NOT NULL   -- rows from before prompt_version was recorded
    AND judged_ts >= current_timestamp() - INTERVAL ${monitor_window_days} DAYS
  GROUP BY ALL
),
r AS (
  SELECT w.*, judged_incorrect / judged AS false_hit_rate,
         (judged_incorrect / judged + 1.9208 / judged
           - 1.96 * sqrt((judged_incorrect / judged) * (1 - judged_incorrect / judged) / judged + 0.9604 / (judged * judged)))
           / (1 + 3.8416 / judged) AS ci_low,
         (judged_incorrect / judged + 1.9208 / judged
           + 1.96 * sqrt((judged_incorrect / judged) * (1 - judged_incorrect / judged) / judged + 0.9604 / (judged * judged)))
           / (1 + 3.8416 / judged) AS ci_high
  FROM w
)
SELECT r.*,
       r.last_judged_ts = max(r.last_judged_ts) OVER () AS is_current_prompt,
       ${false_hit_limit} AS false_hit_limit,
       CASE WHEN judged < ${monitor_min_judged} THEN 'INSUFFICIENT_DATA'
            WHEN ci_low > ${false_hit_limit} THEN 'ALERT'
            WHEN false_hit_rate > ${false_hit_limit} THEN 'WATCH'
            ELSE 'OK' END AS status,
       CASE WHEN judged < ${monitor_min_judged} THEN 'Judge more hits before drawing conclusions.'
            WHEN ci_low > ${false_hit_limit} THEN 'Raise the threshold, or stop caching the categories driving wrong hits (gold_category_risk).'
            WHEN false_hit_rate > ${false_hit_limit} THEN 'Judge more hits; consider raising the threshold.'
            ELSE 'No action needed.' END AS recommended_action,
       current_timestamp() AS evaluated_at
FROM r;
