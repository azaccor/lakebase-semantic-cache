-- The LLM judge's measured false-hit rate per day, with a Wilson 95% interval, and how often it
-- agrees with the labels on replayed (labeled) hits.
CREATE OR REFRESH MATERIALIZED VIEW gold_judge_daily
COMMENT "Daily LLM-judge results on sampled cache hits: judged false-hit rate with a Wilson 95% confidence interval, and judge-vs-label agreement on labeled replay hits. A false hit is a cached answer that does not correctly answer the user's question."
AS
WITH j AS (
  SELECT date(judged_ts) AS judged_date, prompt_version, judge_version, judge_model, source,
         count(*) AS judged,
         count_if(verdict = 'incorrect') AS judged_incorrect,
         count(label_correct) AS labeled,
         count_if(label_correct IS NOT NULL AND (verdict = 'correct') = label_correct) AS judge_label_agree,
         count_if(label_correct = false) AS label_incorrect,
         avg(similarity) AS avg_similarity,
         round(avg(threshold), 2) AS threshold
  FROM ${catalog}.${schema}.judge_results
  WHERE verdict IN ('correct', 'incorrect') AND prompt_version IS NOT NULL   -- rows from before prompt_version was recorded
  GROUP BY ALL
)
SELECT j.*,
       j.prompt_version = (SELECT max_by(prompt_version, judged_ts) FROM ${catalog}.${schema}.judge_results
                           WHERE prompt_version IS NOT NULL) AS is_current_prompt,
       judged_incorrect / judged AS false_hit_rate,
       (judged_incorrect / judged + 1.9208 / judged
         - 1.96 * sqrt((judged_incorrect / judged) * (1 - judged_incorrect / judged) / judged + 0.9604 / (judged * judged)))
         / (1 + 3.8416 / judged) AS false_hit_rate_ci_low,
       (judged_incorrect / judged + 1.9208 / judged
         + 1.96 * sqrt((judged_incorrect / judged) * (1 - judged_incorrect / judged) / judged + 0.9604 / (judged * judged)))
         / (1 + 3.8416 / judged) AS false_hit_rate_ci_high,
       CASE WHEN labeled > 0 THEN judge_label_agree / labeled END AS judge_label_agreement,
       CASE WHEN labeled > 0 THEN label_incorrect / labeled END AS label_false_hit_rate
FROM j;
