# Governed table snapshots

Read through the SQL warehouse at export time.

## gold_cache_daily

`SELECT * FROM gold_cache_daily ORDER BY event_date DESC, requests DESC LIMIT 25`

| event_date | traffic_type | category | money_movement | model | prompt_version | is_current_prompt | backend | threshold | requests | hits | deflection_rate | labeled_hits | labeled_wrong_hits | avg_latency_ms | avg_hit_latency_ms | llm_latency_ms | baseline_cost_per_question_usd | cost_per_question_usd | baseline_llm_cost_usd | llm_cost_usd | savings_usd |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-20 | replay | account_management | false | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.75 | 17 | 6 | 0.35294117647058826 | 6 | 0 | 7.004903176493826 | 7.546282333957303 | 1766.356996584919 | 0.011282452830188678 | 0.0073008106548279675 | 0.19180169811320752 | 0.12411378113207547 | 0.06768791698113207 |
| 2026-10-20 | seed | account_management | false | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.99 | 16 | 16 | 1.0 | 0 | 0 | 247.21389481250532 | 247.21389481250532 | 1766.356996584919 | 0.011282452830188678 | 4.0E-7 | 0.18051924528301885 | 6.4E-6 | 0.18051284528301886 |
| 2026-10-20 | replay | account_access | false | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.75 | 12 | 4 | 0.3333333333333333 | 4 | 0 | 6.792947832915767 | 6.602493999253056 | 1766.356996584919 | 0.011282452830188678 | 0.007522035220125786 | 0.13538943396226413 | 0.09026442264150943 | 0.045125011320754714 |
| 2026-10-20 | replay | security | false | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.75 | 12 | 2 | 0.16666666666666666 | 2 | 0 | 6.563974250032818 | 7.026033999864012 | 1766.356996584919 | 0.011282452830188678 | 0.009402444025157232 | 0.13538943396226413 | 0.11282932830188679 | 0.022560105660377357 |
| 2026-10-20 | seed | payments | true | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.99 | 10 | 10 | 1.0 | 0 | 0 | 227.41807170002062 | 227.41807170002062 | 1766.356996584919 | 0.011282452830188678 | 4.0E-7 | 0.11282452830188679 | 4.0E-6 | 0.11282052830188678 |
| 2026-10-20 | replay | payments | true | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.75 | 10 | 2 | 0.2 | 2 | 0 | 6.942241800061311 | 7.849124500353355 | 1766.356996584919 | 0.011282452830188678 | 0.009026362264150942 | 0.11282452830188679 | 0.09026362264150943 | 0.022560905660377356 |
| 2026-10-20 | seed | card | false | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.99 | 10 | 10 | 1.0 | 0 | 0 | 222.23525570001075 | 222.23525570001075 | 1766.356996584919 | 0.011282452830188678 | 4.0E-7 | 0.11282452830188679 | 4.0E-6 | 0.11282052830188678 |
| 2026-10-20 | replay | card | false | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.75 | 9 | 2 | 0.2222222222222222 | 2 | 0 | 6.74081155537149 | 6.558635000146751 | 1766.356996584919 | 0.011282452830188678 | 0.00877564109014675 | 0.1015420754716981 | 0.07898076981132075 | 0.022561305660377357 |
| 2026-10-20 | seed | account_access | false | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.99 | 8 | 8 | 1.0 | 0 | 0 | 268.99850349998997 | 268.99850349998997 | 1766.356996584919 | 0.011282452830188678 | 4.0E-7 | 0.09025962264150943 | 3.2E-6 | 0.09025642264150943 |
| 2026-10-20 | replay | fees | false | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.75 | 8 | 2 | 0.25 | 2 | 2 | 6.745454125166361 | 6.34519300001557 | 1766.356996584919 | 0.011282452830188678 | 0.008462239622641508 | 0.09025962264150943 | 0.06769791698113206 | 0.02256170566037736 |
| 2026-10-20 | seed | investing | false | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.99 | 8 | 8 | 1.0 | 0 | 0 | 298.25266274998796 | 298.25266274998796 | 1766.356996584919 | 0.011282452830188678 | 4.0E-7 | 0.09025962264150943 | 3.2E-6 | 0.09025642264150943 |
| 2026-10-20 | seed | deposits | true | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.99 | 8 | 8 | 1.0 | 0 | 0 | 200.89417224999195 | 200.89417224999195 | 1766.356996584919 | 0.011282452830188678 | 4.0E-7 | 0.09025962264150943 | 3.2E-6 | 0.09025642264150943 |
| 2026-10-20 | replay | deposits | true | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.75 | 8 | 3 | 0.375 | 3 | 0 | 6.560414375371693 | 6.595417333907487 | 1766.356996584919 | 0.011282452830188678 | 0.007051933018867924 | 0.09025962264150943 | 0.056415464150943395 | 0.03384415849056603 |
| 2026-10-20 | seed | security | false | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.99 | 6 | 6 | 1.0 | 0 | 0 | 230.02877350001918 | 230.02877350001918 | 1766.356996584919 | 0.011282452830188678 | 4.0E-7 | 0.06769471698113207 | 2.4E-6 | 0.06769231698113207 |
| 2026-10-20 | replay | account_details | false | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.75 | 6 | 1 | 0.16666666666666666 | 1 | 0 | 6.941444833501009 | 6.412120999812032 | 1766.356996584919 | 0.011282452830188678 | 0.009402444025157232 | 0.06769471698113207 | 0.05641466415094339 | 0.011280052830188679 |
| 2026-10-20 | replay | investing | false | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.75 | 6 | 1 | 0.16666666666666666 | 1 | 0 | 7.423529166771914 | 6.575534998773946 | 1766.356996584919 | 0.011282452830188678 | 0.009402444025157232 | 0.06769471698113207 | 0.05641466415094339 | 0.011280052830188679 |
| 2026-10-20 | replay | taxes | false | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.75 | 5 | 0 | 0.0 | 0 | 0 | 7.7651094004977494 |  | 1766.356996584919 | 0.011282452830188678 | 0.011282852830188678 | 0.05641226415094339 | 0.056414264150943395 | -2.0E-6 |
| 2026-10-20 | replay | savings | false | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.75 | 5 | 0 | 0.0 | 0 | 0 | 6.365153799924883 |  | 1766.356996584919 | 0.011282452830188678 | 0.011282852830188678 | 0.05641226415094339 | 0.056414264150943395 | -2.0E-6 |
| 2026-10-20 | replay | funding | true | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.75 | 5 | 3 | 0.6 | 3 | 0 | 6.9330856000306085 | 7.027173666453261 | 1766.356996584919 | 0.011282452830188678 | 0.0045133811320754716 | 0.05641226415094339 | 0.022566905660377355 | 0.03384535849056603 |
| 2026-10-20 | replay | withdrawals | true | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.75 | 5 | 1 | 0.2 | 1 | 0 | 6.797024399929796 | 7.4213919997419 | 1766.356996584919 | 0.011282452830188678 | 0.009026362264150942 | 0.05641226415094339 | 0.045131811320754715 | 0.011280452830188678 |
| 2026-10-20 | seed | funding | true | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.99 | 4 | 4 | 1.0 | 0 | 0 | 273.28211324999785 | 273.28211324999785 | 1766.356996584919 | 0.011282452830188678 | 4.0E-7 | 0.04512981132075471 | 1.6E-6 | 0.045128211320754716 |
| 2026-10-20 | seed | fees | false | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.99 | 4 | 4 | 1.0 | 0 | 0 | 306.84179025001157 | 306.84179025001157 | 1766.356996584919 | 0.011282452830188678 | 4.0E-7 | 0.04512981132075471 | 1.6E-6 | 0.045128211320754716 |
| 2026-10-20 | seed | rewards | false | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.99 | 4 | 4 | 1.0 | 0 | 0 | 272.2497544999882 | 272.2497544999882 | 1766.356996584919 | 0.011282452830188678 | 4.0E-7 | 0.04512981132075471 | 1.6E-6 | 0.045128211320754716 |
| 2026-10-20 | seed | limits | true | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.99 | 4 | 4 | 1.0 | 0 | 0 | 217.47771150000972 | 217.47771150000972 | 1766.356996584919 | 0.011282452830188678 | 4.0E-7 | 0.04512981132075471 | 1.6E-6 | 0.045128211320754716 |
| 2026-10-20 | seed | savings | false | databricks-claude-opus-4-8 | 189c61a1 | true | pgvector | 0.99 | 4 | 4 | 1.0 | 0 | 0 | 264.23278100001824 | 264.23278100001824 | 1766.356996584919 | 0.011282452830188678 | 4.0E-7 | 0.04512981132075471 | 1.6E-6 | 0.045128211320754716 |

## gold_judge_daily

`SELECT * FROM gold_judge_daily ORDER BY judged_date DESC LIMIT 25`

| judged_date | prompt_version | judge_version | judge_model | source | judged | judged_incorrect | labeled | judge_label_agree | label_incorrect | avg_similarity | threshold | is_current_prompt | false_hit_rate | false_hit_rate_ci_low | false_hit_rate_ci_high | judge_label_agreement | label_false_hit_rate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-19 | 189c61a1 | d26488e8 | databricks-claude-opus-4-8 | app-replay | 46 | 3 | 46 | 45 | 2 | 0.793538094682882 | 0.75 | true | 0.06521739130434782 | 0.022427454466343564 | 0.17503009103781358 | 0.9782608695652174 | 0.043478260869565216 |
| 2026-10-19 | 189c61a1 | d26488e8 | databricks-claude-opus-4-8 | app | 3 | 1 | 0 | 0 | 0 | 0.8747776125706865 | 0.75 | true | 0.3333333333333333 | 0.061490315276160466 | 0.7923450448735121 |  |  |
| 2026-10-19 | 5ab5339b | d26488e8 | databricks-claude-opus-4-8 | app | 1 | 1 | 0 | 0 | 0 | 0.8022639990527634 | 0.75 | false | 1.0 | 0.20654329147389294 | 1.0 |  |  |
| 2026-10-19 | 5ab5339b | d26488e8 | databricks-claude-opus-4-8 | app-replay | 46 | 7 | 46 | 41 | 2 | 0.7970792823205369 | 0.75 | false | 0.15217391304347827 | 0.0757218623401748 | 0.28224417406315094 | 0.8913043478260869 | 0.043478260869565216 |

## gold_false_hit_monitor

`SELECT * FROM gold_false_hit_monitor ORDER BY last_judged_ts DESC LIMIT 10`

| prompt_version | judge_version | judge_model | judged | judged_incorrect | threshold_in_use | window_start | last_judged_ts | false_hit_rate | ci_low | ci_high | is_current_prompt | false_hit_limit | status | recommended_action | evaluated_at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 189c61a1 | d26488e8 | databricks-claude-opus-4-8 | 49 | 4 | 0.75 | 2026-10-19T22:14:00.184Z | 2026-10-19T23:52:26.757Z | 0.08163265306122448 | 0.03220229624171222 | 0.19189387041486136 | true | 0.10 | OK | No action needed. | 2026-10-20T01:12:59.348Z |
| 5ab5339b | d26488e8 | databricks-claude-opus-4-8 | 47 | 8 | 0.75 | 2026-10-19T21:27:41.135Z | 2026-10-19T21:28:53.375Z | 0.1702127659574468 | 0.08886258091263927 | 0.30140051072885116 | false | 0.10 | WATCH | Judge more hits; consider raising the threshold. | 2026-10-20T01:12:59.348Z |

## gold_threshold_curve

`SELECT * FROM gold_threshold_curve ORDER BY backend, threshold LIMIT 20`

| backend | threshold | repeat_caught_rate | wrong_rate_repeat | wrong_rate_uncached | hit_rate_at_50pct_repeat | wrong_per_request_at_50pct_repeat | account_specific_hits | run_id | run_ts |
|---|---|---|---|---|---|---|---|---|---|
| pgvector | 0.5 | 1.0 | 0.17365269461077845 | 0.96 | 0.98 | 0.5668263473053892 | 8 | 06c73f12-0f34-4f73-b7b3-732ebd20ffb0 | 2026-10-20T01:02:51.372Z |
| pgvector | 0.55 | 0.9760479041916168 | 0.16167664670658682 | 0.8514285714285714 | 0.9137382378100941 | 0.5065526090675792 | 7 | 06c73f12-0f34-4f73-b7b3-732ebd20ffb0 | 2026-10-20T01:02:51.372Z |
| pgvector | 0.6 | 0.9101796407185628 | 0.1377245508982036 | 0.6114285714285714 | 0.7608041060735671 | 0.3745765611633875 | 6 | 06c73f12-0f34-4f73-b7b3-732ebd20ffb0 | 2026-10-20T01:02:51.372Z |
| pgvector | 0.65 | 0.7724550898203593 | 0.10179640718562874 | 0.32571428571428573 | 0.5490846877673226 | 0.21375534644995725 | 5 | 06c73f12-0f34-4f73-b7b3-732ebd20ffb0 | 2026-10-20T01:02:51.372Z |
| pgvector | 0.7 | 0.5329341317365269 | 0.03592814371257485 | 0.09714285714285714 | 0.315038494439692 | 0.066535500427716 | 0 | 06c73f12-0f34-4f73-b7b3-732ebd20ffb0 | 2026-10-20T01:02:51.372Z |
| pgvector | 0.75 | 0.2934131736526946 | 0.011976047904191617 | 0.017142857142857144 | 0.15527801539777586 | 0.01455945252352438 | 0 | 06c73f12-0f34-4f73-b7b3-732ebd20ffb0 | 2026-10-20T01:02:51.372Z |
| pgvector | 0.8 | 0.11377245508982035 | 0.005988023952095809 | 0.005714285714285714 | 0.059743370402053034 | 0.005851154833190762 | 0 | 06c73f12-0f34-4f73-b7b3-732ebd20ffb0 | 2026-10-20T01:02:51.372Z |
| pgvector | 0.85 | 0.029940119760479042 | 0.0 | 0.0 | 0.014970059880239521 | 0.0 | 0 | 06c73f12-0f34-4f73-b7b3-732ebd20ffb0 | 2026-10-20T01:02:51.372Z |
| pgvector | 0.9 | 0.005988023952095809 | 0.0 | 0.0 | 0.0029940119760479044 | 0.0 | 0 | 06c73f12-0f34-4f73-b7b3-732ebd20ffb0 | 2026-10-20T01:02:51.372Z |
| pgvector | 0.95 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 06c73f12-0f34-4f73-b7b3-732ebd20ffb0 | 2026-10-20T01:02:51.372Z |

## gold_category_risk

`SELECT * FROM gold_category_risk ORDER BY threshold, category LIMIT 40`

| backend | category | money_movement | threshold | questions | caught_rate | wrong_rate_cached | wrong_rate_uncached | run_ts |
|---|---|---|---|---|---|---|---|---|
| pgvector | account_access | false | 0.600000 | 15 | 0.8666666666666667 | 0.0 | 0.5333333333333333 | 2026-10-20T01:02:51.372Z |
| pgvector | account_details | false | 0.600000 | 6 | 0.8333333333333334 | 0.0 | 0.5 | 2026-10-20T01:02:51.372Z |
| pgvector | account_management | false | 0.600000 | 25 | 0.64 | 0.2 | 0.48 | 2026-10-20T01:02:51.372Z |
| pgvector | account_specific | false | 0.600000 | 8 | 0.0 | 0.75 | 0.75 | 2026-10-20T01:02:51.372Z |
| pgvector | card | false | 0.600000 | 16 | 0.875 | 0.0625 | 0.625 | 2026-10-20T01:02:51.372Z |
| pgvector | credit | false | 0.600000 | 3 | 1.0 | 0.0 | 0.6666666666666666 | 2026-10-20T01:02:51.372Z |
| pgvector | deposits | true | 0.600000 | 13 | 0.7692307692307693 | 0.23076923076923078 | 0.7692307692307693 | 2026-10-20T01:02:51.372Z |
| pgvector | disputes | true | 0.600000 | 4 | 0.5 | 0.25 | 0.25 | 2026-10-20T01:02:51.372Z |
| pgvector | fees | false | 0.600000 | 7 | 0.5714285714285714 | 0.2857142857142857 | 0.7142857142857143 | 2026-10-20T01:02:51.372Z |
| pgvector | funding | true | 0.600000 | 8 | 0.75 | 0.25 | 0.875 | 2026-10-20T01:02:51.372Z |
| pgvector | investing | false | 0.600000 | 13 | 0.9230769230769231 | 0.0 | 0.6153846153846154 | 2026-10-20T01:02:51.372Z |
| pgvector | limits | true | 0.600000 | 8 | 1.0 | 0.0 | 0.75 | 2026-10-20T01:02:51.372Z |
| pgvector | payments | true | 0.600000 | 16 | 0.875 | 0.125 | 0.75 | 2026-10-20T01:02:51.372Z |
| pgvector | rewards | false | 0.600000 | 7 | 0.7142857142857143 | 0.0 | 0.14285714285714285 | 2026-10-20T01:02:51.372Z |
| pgvector | savings | false | 0.600000 | 6 | 0.6666666666666666 | 0.16666666666666666 | 0.5 | 2026-10-20T01:02:51.372Z |
| pgvector | security | false | 0.600000 | 9 | 0.8888888888888888 | 0.1111111111111111 | 0.4444444444444444 | 2026-10-20T01:02:51.372Z |
| pgvector | taxes | false | 0.600000 | 4 | 0.25 | 0.5 | 0.5 | 2026-10-20T01:02:51.372Z |
| pgvector | withdrawals | true | 0.600000 | 7 | 0.5714285714285714 | 0.42857142857142855 | 1.0 | 2026-10-20T01:02:51.372Z |
| pgvector | account_access | false | 0.650000 | 15 | 0.8 | 0.0 | 0.2 | 2026-10-20T01:02:51.372Z |
| pgvector | account_details | false | 0.650000 | 6 | 0.6666666666666666 | 0.0 | 0.3333333333333333 | 2026-10-20T01:02:51.372Z |
| pgvector | account_management | false | 0.650000 | 25 | 0.56 | 0.12 | 0.16 | 2026-10-20T01:02:51.372Z |
| pgvector | account_specific | false | 0.650000 | 8 | 0.0 | 0.625 | 0.625 | 2026-10-20T01:02:51.372Z |
| pgvector | card | false | 0.650000 | 16 | 0.75 | 0.0625 | 0.25 | 2026-10-20T01:02:51.372Z |
| pgvector | credit | false | 0.650000 | 3 | 1.0 | 0.0 | 0.0 | 2026-10-20T01:02:51.372Z |
| pgvector | deposits | true | 0.650000 | 13 | 0.6923076923076923 | 0.15384615384615385 | 0.5384615384615384 | 2026-10-20T01:02:51.372Z |
| pgvector | disputes | true | 0.650000 | 4 | 0.25 | 0.25 | 0.25 | 2026-10-20T01:02:51.372Z |
| pgvector | fees | false | 0.650000 | 7 | 0.5714285714285714 | 0.2857142857142857 | 0.5714285714285714 | 2026-10-20T01:02:51.372Z |
| pgvector | funding | true | 0.650000 | 8 | 0.625 | 0.25 | 0.375 | 2026-10-20T01:02:51.372Z |
| pgvector | investing | false | 0.650000 | 13 | 0.8461538461538461 | 0.0 | 0.46153846153846156 | 2026-10-20T01:02:51.372Z |
| pgvector | limits | true | 0.650000 | 8 | 0.875 | 0.0 | 0.625 | 2026-10-20T01:02:51.372Z |
| pgvector | payments | true | 0.650000 | 16 | 0.6875 | 0.125 | 0.3125 | 2026-10-20T01:02:51.372Z |
| pgvector | rewards | false | 0.650000 | 7 | 0.5714285714285714 | 0.0 | 0.0 | 2026-10-20T01:02:51.372Z |
| pgvector | savings | false | 0.650000 | 6 | 0.5 | 0.16666666666666666 | 0.16666666666666666 | 2026-10-20T01:02:51.372Z |
| pgvector | security | false | 0.650000 | 9 | 0.7777777777777778 | 0.1111111111111111 | 0.2222222222222222 | 2026-10-20T01:02:51.372Z |
| pgvector | taxes | false | 0.650000 | 4 | 0.25 | 0.25 | 0.25 | 2026-10-20T01:02:51.372Z |
| pgvector | withdrawals | true | 0.650000 | 7 | 0.5714285714285714 | 0.14285714285714285 | 0.5714285714285714 | 2026-10-20T01:02:51.372Z |
| pgvector | account_access | false | 0.700000 | 15 | 0.7333333333333333 | 0.0 | 0.13333333333333333 | 2026-10-20T01:02:51.372Z |
| pgvector | account_details | false | 0.700000 | 6 | 0.5 | 0.0 | 0.16666666666666666 | 2026-10-20T01:02:51.372Z |
| pgvector | account_management | false | 0.700000 | 25 | 0.36 | 0.04 | 0.04 | 2026-10-20T01:02:51.372Z |
| pgvector | account_specific | false | 0.700000 | 8 | 0.0 | 0.0 | 0.0 | 2026-10-20T01:02:51.372Z |

## silver_faq_intents

`SELECT * FROM silver_faq_intents ORDER BY category, intent_id LIMIT 60`

| intent_id | category | money_movement | canonical_question | reference_answer | cacheable | non_cacheable_reason | n_paraphrases | source_file |
|---|---|---|---|---|---|---|---|---|
| account_frozen | account_access | false | Why is my account locked or frozen? | Accounts are sometimes temporarily locked for security reviews, unusual activity, or verification needs. Check the app for any prompts to confirm your identity or a recent transaction; completing them | true |  | 4 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| pin_reset | account_access | false | How do I reset my PIN? | Open the app, go to the Card tab, tap your card, then select Change PIN. You'll verify your identity and can set a new 4-digit PIN. No fee, effective immediately. | true |  | 4 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| reactivate_account | account_access | false | How do I reopen a closed account? | A permanently closed account generally can't be reopened; you'd sign up for a new account. If your account was only locked or paused, completing any verification prompts usually restores access—contac | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| verify_identity | account_access | false | How do I verify my identity? | Provide your full name, date of birth, and the last 4 digits of your SSN in the app when prompted. Occasionally a photo of a government ID is required. Verification unlocks higher sending and withdraw | true |  | 4 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| account_number_routing | account_details | false | Where do I find my account and routing number? | Open the Money tab and tap the direct deposit or account details option to view your account and routing numbers. You can copy them or share a prefilled direct-deposit form with your employer. | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| download_statement | account_details | false | How do I download my account statement? | Monthly statements and transaction exports are available under Profile > Documents > Statements. You can view or download a PDF, and export activity as a CSV for a date range you choose. | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| business_account | account_management | false | Can I accept payments for my business? | You can switch to or create a business account to accept payments from customers, which may be subject to a small per-transaction fee. Business payments have different tax reporting, and you can view  | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| close_account | account_management | false | How do I close my account? | First cash out any remaining balance. Then go to Profile > Support > Something Else > Account Settings > Close My Account. Closure is permanent and your transaction history will no longer be accessibl | true |  | 4 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| notification_settings | account_management | false | How do I change my notification settings? | Open Profile > Notifications to control push, SMS, and email alerts for payments, deposits, and security events. Security-related alerts may be required and can't be fully disabled. | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| overdraft_coverage | account_management | false | Do you charge overdraft fees? | We don't charge overdraft fees. Transactions that exceed your available balance are generally declined, though eligible accounts may have a small no-fee overdraft coverage buffer shown in the app. | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| paycheck_advance | account_management | false | Can I get paid early or access an advance? | With eligible direct deposit you can be paid up to two days early automatically. Some users may qualify for a small no-interest advance shown in the app; eligibility and limits depend on your deposit  | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| spending_insights | account_management | false | Where can I see my spending by category? | The Insights or Spending section groups your transactions by category and merchant and shows monthly trends. You can tap a category to see the underlying transactions and set optional budget alerts. | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| teen_account | account_management | false | Can a teenager use the app? | Teens within the supported age range can use a sponsored account approved and managed by a parent or guardian, who can view activity and set controls. A guardian starts the process from their own acco | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| update_contact_info | account_management | false | How do I update my phone number or email? | Go to Profile > Personal Information to update your email or phone number. You'll verify the new contact with a confirmation code. Keeping these current is important for security alerts and account re | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| my_balance | account_specific | false | What is my current balance? | ACCOUNT-SPECIFIC: must be answered from the authenticated user's live account data, never from a shared cache. | false | Answer is per-user and changes constantly; a shared semantic cache would leak or serve stale/incorrect balances. | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| why_my_transfer_pending | account_specific | false | Why is my transfer still pending? | ACCOUNT-SPECIFIC: depends on the individual transaction's state; general guidance may be cacheable but the specific status must come from the user's live data. | false | Textually similar to a general FAQ but requires the specific transaction's live status; demonstrates why scope/partition keys and confidence gating matter. | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| card_activation | card | false | How do I activate my new card? | In the app, open the Card tab and tap Activate Card. Scan the QR code on the sticker, or enter the CVV and expiration manually. Activation is instant. | true |  | 4 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| card_declined | card | false | Why was my card declined? | Common reasons include insufficient balance, the card being locked, an unverified account, exceeding a spending limit, or the merchant being flagged. Check your balance and card status in the app; con | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| freeze_card | card | false | How do I temporarily lock my card? | Open the Card tab and toggle Lock Card. This instantly pauses new spending while keeping the card active; toggle it off anytime to resume. Recurring subscriptions may still process depending on settin | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| lost_stolen_card | card | false | What do I do if my card is lost or stolen? | In the app, open the Card tab and select Disable Card to immediately block use. Report it as lost or stolen, and order a free replacement, which arrives in about a week. Your card number changes for s | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| virtual_card | card | false | How do I get a virtual card for online purchases? | A virtual card is available instantly in the Card tab for online and in-app purchases, and can be added to your mobile wallet. You can view its number, expiration, and CVV in the app, and generate a n | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| credit_building | credit | false | How does the credit-building feature work? | The credit-building product typically uses a secured card tied to your balance; on-time activity is reported to the credit bureaus to help build history. Enroll in the Credit section and review the te | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| direct_deposit_timing | deposits | true | When will my direct deposit arrive? | Direct deposits post as soon as we receive them from your employer or payer, which can be up to 2 days before your scheduled payday. Timing depends on when the sender submits the deposit. | true |  | 4 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| mobile_check_deposit | deposits | true | How do I deposit a check from my phone? | In the app, go to the Money or Deposit section, select Deposit a Check, then photograph the front and back after endorsing it. Funds are typically available within a few business days; larger checks m | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| set_up_direct_deposit | deposits | true | How do I set up direct deposit? | Find your account and routing numbers under the Money tab, then give them to your employer or fill out their direct-deposit form (the app can generate one). Deposits begin on your next pay cycle once  | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| tax_refund_deposit | deposits | true | Can I receive my tax refund in the app? | Yes—provide your app account and routing numbers on your tax return for direct deposit. Refunds often arrive a bit sooner than a mailed check, and you may get them up to a couple days early once the I | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| dispute_charge | disputes | true | How do I dispute a charge I don't recognize? | Open the transaction in your Activity feed, tap it, then select Need Help & Report. Choose Dispute and follow the prompts. We'll investigate and may issue a provisional credit while the claim is revie | true |  | 4 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| fees_overview | fees | false | What fees does the app charge? | Sending and receiving money, standard cash out, and using your card are free. Fees apply to instant cash out, ATM withdrawals outside the free network, and certain crypto/stock transactions. | true |  | 4 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| foreign_transaction | fees | false | Are there fees for using my card abroad? | There's no foreign transaction fee on card purchases; transactions are converted at the network exchange rate. ATM operators abroad may charge their own fees, and out-of-network ATM fees still apply. | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| add_money | funding | true | How do I add money to my balance? | Tap the Money tab, then Add Cash, enter an amount, and confirm. Funds pull from your linked bank account and are typically available instantly. | true |  | 4 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| change_linked_bank | funding | true | How do I change my linked bank account? | Go to the Money tab, tap the linked bank or card, then select Replace or Remove. Add the new account by entering its details or logging in through your bank. Instant transfers require a debit card. | true |  | 4 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| buy_bitcoin | investing | false | How do I buy Bitcoin in the app? | Open the Bitcoin (or Crypto) tab, tap Buy, enter a dollar amount, choose your funding source, and confirm. You can buy fractional amounts. Standard disclosures and any applicable fees are shown before | true |  | 4 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| buy_stock | investing | false | How do I buy stocks in the app? | Open the Investing tab, search for a company, tap Buy, and enter a dollar amount—you can buy fractional shares. Orders execute during market hours; disclosures and any fees are shown before you confir | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| crypto_withdrawal | investing | false | How do I withdraw Bitcoin to an external wallet? | In the Bitcoin tab, choose Withdraw, enter the destination wallet address, and confirm. Enable withdrawals if it's your first time (may require identity verification). Network fees apply and on-chain  | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| sell_stock | investing | false | How do I sell a stock and withdraw the proceeds? | In the Investing tab, open the holding, tap Sell, and choose an amount. Sales execute during market hours; proceeds settle after a couple of business days before you can withdraw them to your balance  | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| atm_limits | limits | true | What are the ATM withdrawal limits? | You can withdraw up to $1,000 per transaction, $1,000 per ATM withdrawal per day, and $1,000 per 7-day period, with a limit on the number of withdrawals per day. Third-party ATM operator limits may al | true |  | 4 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| transfer_limits | limits | true | What are the limits on sending money? | New accounts can send up to $250 per 7 days. After you verify your identity (name, DOB, last 4 of SSN), sending limits increase substantially. Limits are shown in Settings > Limits. | true |  | 4 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| cancel_pending_payment | payments | true | Can I cancel a payment I already sent? | If the payment is still pending you may be able to cancel it from the Activity feed. Payments to other users are usually instant and can't be reversed—ask the recipient to send it back. Contact suppor | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| recurring_payments | payments | true | How do I manage recurring or scheduled payments? | Scheduled and recurring payments are managed in the Activity or Scheduled section, where you can create, edit, pause, or cancel them. Changes apply to future payments; a payment already in progress ca | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| refund_timing | payments | true | How long do refunds take to show up? | Most merchant refunds appear within 1–5 business days, depending on when the merchant releases them. Instant refunds from other users of the app are immediate. | true |  | 4 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| request_money | payments | true | How do I request money from someone? | On the payment screen, enter the amount, select Request instead of Pay, choose the recipient, add an optional note, and send. They'll get a notification and can approve the request to pay you. | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| split_payment | payments | true | How do I split a bill with friends? | Use the split or request feature to divide an amount evenly (or custom) across multiple recipients and send each person a request. As they pay, you'll see the payments arrive in your Activity. | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| gift_card_boosts | rewards | false | How do instant discounts or boosts work? | Boosts are instant discounts you activate in the Card tab and apply automatically when you pay with your card at eligible merchants. You can have one active at a time and switch it whenever you like. | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| referral_bonus | rewards | false | How does the referral bonus work? | Share your referral code from the Profile tab. When a new user signs up with your code and completes a qualifying transaction (e.g., sends a set amount within the promo window), you both receive the a | true |  | 4 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| round_ups | savings | false | How do round-ups to savings work? | Enable round-ups in the Savings settings to round each card purchase up to the nearest dollar and move the difference into savings automatically. You can turn it off or adjust it anytime. | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| savings_interest | savings | false | Does the app pay interest on savings? | If you have a savings balance or eligible account, interest accrues daily and pays out monthly at the current advertised rate, which can change over time. Terms and any eligibility requirements are sh | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| biometric_login | security | false | How do I enable Face ID or fingerprint login? | Under Profile > Security, toggle on biometric login (Face ID / fingerprint). Your device stores the biometric data; the app only receives an approval, so your biometrics are never shared with us. | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| scam_protection | security | false | How do I protect myself from scams? | Only send money to people you know and trust—payments are like cash and often can't be reversed. Never share your PIN, sign-in code, or account details, and ignore anyone pressuring you to pay to 'cla | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| two_factor_auth | security | false | How do I turn on two-factor authentication? | In Profile > Security, enable two-factor authentication and choose SMS, an authenticator app, or biometrics. After that, sign-ins and sensitive actions require a second verification step. | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| tax_documents | taxes | false | Where can I find my tax documents? | Tax documents (such as a 1099-B for investing activity) are available under Profile > Documents > Tax Documents once they're issued, typically by mid-February for the prior tax year. | true |  | 4 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| atm_locator | withdrawals | true | How do I find a free ATM? | Use the ATM locator in the app to find in-network ATMs where withdrawals are free. Out-of-network machines may charge a fee and the operator may add a surcharge; some accounts offer monthly fee reimbu | true |  | 3 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |
| cash_out_timing | withdrawals | true | How long does it take to cash out to my bank? | Standard cash out is free and arrives in 1–3 business days. Instant cash out reaches your linked debit card in minutes for a small fee (a percentage of the amount). | true |  | 4 | /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json |

## eval_summary

`SELECT * FROM eval_summary ORDER BY run_ts DESC LIMIT 5`

| backend | threshold | hit_rate | precision | false_hit_rate | account_specific_hits | baseline_ms | cached_avg_ms | hit_ms | miss_ms | baseline_cost_per_1k | cached_cost_per_1k | latency_saved_pct | cost_saved_pct | run_id | run_ts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pgvector | 0.75 | 0.28 | 0.9591836734693877 | 0.011428571428571429 | 0.0 | 1756.897417450989 | 1489.6385979223421 | 215.04863355999208 | 1985.3124729521448 | 11.253529411764706 | 8.102541176470588 | 0.1521197634386655 | 0.28 | 06c73f12-0f34-4f73-b7b3-732ebd20ffb0 | 2026-10-20T01:02:51.372Z |
| pgvector | 0.75 | 0.28 | 0.9591836734693877 | 0.011428571428571429 | 0.0 | 1756.897417450989 | 1487.3794642023493 | 212.78949983999934 | 1983.053339232152 | 11.253529411764706 | 8.102541176470588 | 0.15340562890670784 | 0.28 | 19b100ec-f5ee-44a6-bea4-eb2f07bd9c1f | 2026-10-20T00:41:30.380Z |
| pgvector | 0.75 | 0.28 | 0.9591836734693877 | 0.011428571428571429 | 0.0 | 1756.897417450989 | 1499.6554821566333 | 225.0655177942833 | 1995.329357186436 | 11.253529411764706 | 8.102541176470588 | 0.1464183012276138 | 0.28 | d120b95b-204e-4839-811b-153539d0293a | 2026-10-19T23:11:52.523Z |
| pgvector | 0.75 | 0.28 | 0.9591836734693877 | 0.011428571428571429 | 0.0 | 1761.1314898200064 | 1484.0393418297135 | 206.4198681657133 | 1980.8913593657137 | 33.789300000000004 | 24.328295999999998 | 0.15733756939330668 | 0.28000000000000014 | 452e0362-29b4-430d-ae65-a3fa5788d54a | 2026-10-19T22:13:25.147Z |
| pgvector | 0.75 | 0.28 | 0.9591836734693877 | 0.011428571428571429 | 0.0 | 2646.9129922179504 | 2124.4068933010976 | 207.82306680571176 | 2869.7450480493035 | 18.510480769230764 | 13.32754615384615 | 0.19740206816508343 | 0.28 | d9637673-2551-47e9-851c-3058227e8884 | 2026-10-19T22:08:04.698Z |

## load_test_latency

`SELECT * FROM load_test_latency ORDER BY run_id, size, clients LIMIT 40`

| size | backend | clients | requests | qps | p50_ms | p95_ms | p99_ms | run_id | lakebase_cu |
|---|---|---|---|---|---|---|---|---|---|
| 1000 | pgvector | 1 | 4270 | 142.33333333333334 | 6.615864500020052 | 9.28586430004543 | 13.52327231008078 | 7a3719f3-ee8b-46c1-866c-ea3860c906ac | 1 |
| 1000 | pgvector | 4 | 8632 | 287.73333333333335 | 12.237921500002358 | 24.583177250025297 | 38.45010485005344 | 7a3719f3-ee8b-46c1-866c-ea3860c906ac | 1 |
| 1000 | pgvector | 16 | 8537 | 284.56666666666666 | 52.3001800000884 | 98.22065380001277 | 152.32544472008564 | 7a3719f3-ee8b-46c1-866c-ea3860c906ac | 1 |
| 1000 | pgvector | 32 | 8313 | 277.1 | 88.31232699992597 | 298.97477380002323 | 423.2207640799856 | 7a3719f3-ee8b-46c1-866c-ea3860c906ac | 1 |
| 10000 | pgvector | 1 | 3915 | 130.5 | 7.309587999998257 | 9.99512330000698 | 12.75938783995572 | 7a3719f3-ee8b-46c1-866c-ea3860c906ac | 1 |
| 10000 | pgvector | 4 | 8776 | 292.53333333333336 | 12.036802500063004 | 23.98118350004097 | 34.200853249984675 | 7a3719f3-ee8b-46c1-866c-ea3860c906ac | 1 |
| 10000 | pgvector | 16 | 8324 | 277.46666666666664 | 49.9640825000256 | 135.39226195003374 | 189.0561780199483 | 7a3719f3-ee8b-46c1-866c-ea3860c906ac | 1 |
| 10000 | pgvector | 32 | 8420 | 280.6666666666667 | 104.92572849994986 | 173.14882470006404 | 256.04566099006547 | 7a3719f3-ee8b-46c1-866c-ea3860c906ac | 1 |
| 100000 | pgvector | 1 | 2704 | 90.13333333333334 | 10.828463999928317 | 14.880169200148426 | 17.911573339861178 | 7a3719f3-ee8b-46c1-866c-ea3860c906ac | 1 |
| 100000 | pgvector | 4 | 6112 | 203.73333333333332 | 18.696292999948128 | 31.899029899818743 | 38.56247270017548 | 7a3719f3-ee8b-46c1-866c-ea3860c906ac | 1 |
| 100000 | pgvector | 16 | 6478 | 215.93333333333334 | 70.3004569999166 | 138.1191091500568 | 171.85624689005607 | 7a3719f3-ee8b-46c1-866c-ea3860c906ac | 1 |
| 100000 | pgvector | 32 | 6185 | 206.16666666666666 | 133.17328499988434 | 352.1779499999864 | 481.86563480008743 | 7a3719f3-ee8b-46c1-866c-ea3860c906ac | 1 |
| 100000 | pgvector | 1 | 2567 | 85.56666666666666 | 11.481341000035172 | 15.25688120000268 | 18.327211459982212 | 9873b55f-e6d8-43b2-99e9-6a0cbc5369be | 1 |
| 100000 | pgvector | 4 | 6218 | 207.26666666666668 | 18.501313499996286 | 31.127611099987003 | 37.055063150075966 | 9873b55f-e6d8-43b2-99e9-6a0cbc5369be | 1 |
| 100000 | pgvector | 16 | 6558 | 218.6 | 69.12918199992646 | 137.82174985000208 | 179.91443381997564 | 9873b55f-e6d8-43b2-99e9-6a0cbc5369be | 1 |
| 100000 | pgvector | 32 | 6436 | 214.53333333333333 | 126.73964399999704 | 341.25596225001686 | 470.88953824996906 | 9873b55f-e6d8-43b2-99e9-6a0cbc5369be | 1 |
| 1000 | pgvector | 1 | 4216 | 140.53333333333333 | 6.62830099997791 | 9.361574250021931 | 12.8560518000143 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 1000 | lakebase_search | 1 | 5002 | 166.73333333333332 | 5.610577499965075 | 7.916332849953277 | 10.89684282993743 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 1000 | lakebase_search | 4 | 14496 | 483.2 | 7.539975000042887 | 12.978916000037088 | 18.631903699969143 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 1000 | pgvector | 4 | 9490 | 316.3333333333333 | 11.098522000054345 | 21.2090797500025 | 29.943614489955063 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 1000 | pgvector | 16 | 9341 | 311.3666666666667 | 40.04581499998494 | 129.42927799997506 | 175.0539546000482 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 1000 | lakebase_search | 16 | 14082 | 469.4 | 25.882294499979253 | 87.28905925003114 | 124.66291097999832 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 1000 | pgvector | 32 | 9224 | 307.46666666666664 | 79.17416349994255 | 274.3651037499832 | 380.45182740998945 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 1000 | lakebase_search | 32 | 13489 | 449.6333333333333 | 50.15008099996976 | 203.70361620005022 | 290.11285880000247 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 10000 | lakebase_search | 1 | 4770 | 159.0 | 5.955432499945346 | 7.9934748499795205 | 10.0839222099785 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 10000 | pgvector | 1 | 3911 | 130.36666666666667 | 7.3428800001238415 | 9.632797500103152 | 12.106487899950482 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 10000 | pgvector | 4 | 9686 | 322.8666666666667 | 11.011319999965963 | 20.277586499958034 | 28.090259599935017 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 10000 | lakebase_search | 4 | 14115 | 470.5 | 7.746238999970956 | 13.17293410008915 | 19.387267600004666 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 10000 | pgvector | 16 | 9631 | 321.03333333333336 | 38.8204879998284 | 124.97670750008183 | 173.54532700005677 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 10000 | lakebase_search | 16 | 14583 | 486.1 | 25.418792000209578 | 80.04862349994255 | 118.82567655996354 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 10000 | pgvector | 32 | 9359 | 311.96666666666664 | 77.03404800008684 | 269.7934161000604 | 385.2424066600406 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 10000 | lakebase_search | 32 | 14512 | 483.73333333333335 | 47.362085500026296 | 180.7683601499661 | 260.2873713500139 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 100000 | lakebase_search | 1 | 4216 | 140.53333333333333 | 6.597447999865835 | 9.83454325000821 | 14.340268299974976 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 100000 | pgvector | 1 | 2424 | 80.8 | 11.895392000042193 | 16.4900481500581 | 21.35252472994352 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 100000 | lakebase_search | 4 | 12338 | 411.26666666666665 | 8.64372549995096 | 16.225185999962832 | 25.45950212006346 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 100000 | pgvector | 4 | 6751 | 225.03333333333333 | 15.75231500009977 | 30.977788999962286 | 45.84117799993237 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 100000 | pgvector | 16 | 6805 | 226.83333333333334 | 58.824542000138536 | 163.74074540003653 | 236.16491339998905 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 100000 | lakebase_search | 16 | 11714 | 390.46666666666664 | 37.713228499910656 | 66.10972804993482 | 91.73246771010783 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 100000 | pgvector | 32 | 6969 | 232.3 | 125.36103100001128 | 265.4827551999914 | 394.7862858800636 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
| 100000 | lakebase_search | 32 | 12044 | 401.46666666666664 | 55.55569499995272 | 224.33034185002046 | 326.5696919600417 | a9ab8878-62aa-43c2-8d71-0e6bc46a2cf0 |  |
