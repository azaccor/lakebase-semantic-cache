# Task `seed_cache` (job run 32232528631469)

Result: **SUCCESS**, 2026-10-20 01:01:12 UTC – 2026-10-20 01:02:30 UTC.

# 01 · Build the cache

Seeds the cache with answers to known FAQs by running them through the LLM endpoint
**via the cache itself** (`get_or_generate`), so seeding exercises the same code path as
live traffic and every request is logged to the `cache_events` Delta table.

- **Dataset:** `silver_faq_intents`, built by the `semantic_cache_ingest` Lakeflow pipeline from the raw
  question bank: 50 support FAQs for Lux Pay, a fictional consumer P2P money app, each with a canonical
  question, a category and a reference answer (its held-out paraphrases are `silver_eval_questions`, used
  in `02_evaluate`). Two account-specific intents are marked `cacheable = false` and are *not* seeded.
- **Scope:** every entry is tagged with the model and a `prompt_version` derived from a hash of
  the system prompt, so editing the prompt automatically starts a fresh cache partition.
- **Idempotent:** seeding uses a 0.99 threshold, so only an (almost) identical question counts as
  already cached. Re-running costs nothing; similar-but-different FAQs don't block each other.

```python
dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "semantic_cache")
dbutils.widgets.text("sdk_wheel", "/Volumes/main/semantic_cache/libs/databricks_lakebase_adapters-<version>-py3-none-any.whl")
dbutils.widgets.text("lakebase_instance", "semantic-cache")
dbutils.widgets.dropdown("backend", "pgvector", ["pgvector", "lakebase_search"])
dbutils.widgets.text("pg_schema", "semantic_cache")   # Postgres schema for the cache tables
dbutils.widgets.text("embedding_endpoint", "databricks-qwen3-embedding-0-6b")
dbutils.widgets.text("llm_endpoint", "databricks-claude-opus-4-8")
# USD per 1M tokens: list-price assumptions for cost estimates; adjust to your contract.
dbutils.widgets.text("price_in_per_m", "5")
dbutils.widgets.text("price_out_per_m", "25")
```

```python
sdk_wheel = dbutils.widgets.get("sdk_wheel")
%pip install -q "{sdk_wheel}[pgvector,lakebase-search]" "databricks-sdk>=0.86"
dbutils.library.restartPython()
```

```python
import hashlib, json, os, sys, uuid

sys.path.insert(0, os.path.abspath(".."))
from semantic_cache import CacheConfig, SemanticCache, chat_generator, log_events

catalog, schema = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
events_table = f"{catalog}.{schema}.cache_events"
llm_endpoint = dbutils.widgets.get("llm_endpoint")
price_in, price_out = float(dbutils.widgets.get("price_in_per_m")), float(dbutils.widgets.get("price_out_per_m"))

cfg = CacheConfig(
    lakebase_instance=dbutils.widgets.get("lakebase_instance"),
    backend=dbutils.widgets.get("backend"),
    pg_schema=dbutils.widgets.get("pg_schema"),
    embedding_endpoint=dbutils.widgets.get("embedding_endpoint"),
)
cache = SemanticCache(cfg)
```

```python
# Shared with 02_evaluate and the app: the prompt's hash is part of the cache scope.
with open("../data/system_prompt.txt") as f:
    SYSTEM_PROMPT = f.read().strip()
scope = {
    "model": llm_endpoint,
    "prompt_version": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:8],
    "tenant": "",
}
generate = chat_generator(llm_endpoint, system_prompt=SYSTEM_PROMPT, max_tokens=400)
scope
```

Output:

```text
{'model': 'databricks-claude-opus-4-8',
 'prompt_version': '189c61a1',
 'tenant': ''}
```

```python
seed = [r.asDict() for r in spark.table(f"{catalog}.{schema}.silver_faq_intents")
        .where("cacheable").orderBy("intent_id").collect()]
print(f"{len(seed)} cacheable intents to seed, from {catalog}.{schema}.silver_faq_intents")
```

Output:

```text
50 cacheable intents to seed, from <catalog>.semantic_cache.silver_faq_intents
```

## Seed

```python
run_id = str(uuid.uuid4())
results = []
for intent in seed:
    r = cache.get_or_generate(
        intent["canonical_question"], generate, scope, threshold=0.99,
        metadata={"intent_id": intent["intent_id"], "category": intent["category"], "source": "seed"},
    )
    results.append(r)
    print(f"{'cached ' if r.hit else 'seeded '} {r.total_ms:7.0f} ms  {intent['canonical_question']}")

log_events(spark, events_table, results, run_id=run_id, source="01_build_cache", backend=cfg.backend,
           price_in_per_m=price_in, price_out_per_m=price_out,
           attributes=[{"intent_id": i["intent_id"]} for i in seed])

# `lakebase_ann` is an IVF index: it learns its clusters from the rows present when it is built,
# and 00_setup built it on an empty table. Rebuilding after the initial seed is cheap at this size.
# (In production, rebuild periodically as the cache grows; HNSW doesn't need this.)
if cache.backend.rebuild_after_bulk_load and cache.backend.row_count() < 100_000:
    cache.backend.rebuild_index()
```

Output:

```text
cached      336 ms  Why is my account locked or frozen?
cached      277 ms  Where do I find my account and routing number?
cached      263 ms  How do I add money to my balance?
cached      188 ms  What are the ATM withdrawal limits?
cached      275 ms  How do I find a free ATM?
cached      453 ms  How do I enable Face ID or fingerprint login?
cached      296 ms  Can I accept payments for my business?
cached      290 ms  How do I buy Bitcoin in the app?
cached      211 ms  How do I buy stocks in the app?
cached      278 ms  Can I cancel a payment I already sent?
cached      275 ms  How do I activate my new card?
cached      190 ms  Why was my card declined?
cached      292 ms  How long does it take to cash out to my bank?
cached      293 ms  How do I change my linked bank account?
cached      218 ms  How do I close my account?
cached      272 ms  How does the credit-building feature work?
cached      275 ms  How do I withdraw Bitcoin to an external wallet?
cached      181 ms  When will my direct deposit arrive?
cached      189 ms  How do I dispute a charge I don't recognize?
cached      276 ms  How do I download my account statement?
cached      299 ms  What fees does the app charge?
cached      465 ms  Are there fees for using my card abroad?
cached      194 ms  How do I temporarily lock my card?
cached      199 ms  How do instant discounts or boosts work?
cached      291 ms  What do I do if my card is lost or stolen?
cached      181 ms  How do I deposit a check from my phone?
cached      121 ms  How do I change my notification settings?
cached      290 ms  Do you charge overdraft fees?
cached      190 ms  Can I get paid early or access an advance?
cached      292 ms  How do I reset my PIN?
cached      193 ms  How do I reopen a closed account?
cached      291 ms  How do I manage recurring or scheduled payments?
cached      271 ms  How does the referral bonus work?
cached      201 ms  How long do refunds take to show up?
cached      189 ms  How do I request money from someone?
cached      196 ms  How do round-ups to savings work?
cached      189 ms  Does the app pay interest on savings?
cached      121 ms  How do I protect myself from scams?
cached      289 ms  How do I sell a stock and withdraw the proceeds?
cached      198 ms  How do I set up direct deposit?
cached      195 ms  Where can I see my spending by category?
cached      200 ms  How do I split a bill with friends?
cached      404 ms  Where can I find my tax documents?
cached      281 ms  Can I receive my tax refund in the app?
cached      280 ms  Can a teenager use the app?
cached      196 ms  What are the limits on sending money?
cached      210 ms  How do I turn on two-factor authentication?
cached      185 ms  How do I update my phone number or email?
cached      415 ms  How do I verify my identity?
cached      207 ms  How do I get a virtual card for online purchases?
```

## Summary

```python
display(spark.sql(f"""
  SELECT count(*)                                   AS requests,
         count_if(NOT hit)                          AS llm_calls,
         round(avg(IF(NOT hit, generate_ms, NULL))) AS avg_llm_ms,
         round(avg(embed_ms))                       AS avg_embed_ms,
         round(avg(lookup_ms), 1)                   AS avg_lookup_ms,
         sum(input_tokens)                          AS input_tokens,
         sum(output_tokens)                         AS output_tokens,
         round(sum(cost_usd), 3)                    AS llm_cost_usd,
         round(avg(IF(NOT hit, cost_usd, NULL)), 4) AS cost_per_llm_call_usd
  FROM {events_table} WHERE run_id = '{run_id}'
"""))
cache.stats()
```

Output:

| requests | llm_calls | avg_llm_ms | avg_embed_ms | avg_lookup_ms | input_tokens | output_tokens | llm_cost_usd | cost_per_llm_call_usd |
|---|---|---|---|---|---|---|---|---|
| 50 | 0 |  | 232.0 | 10.9 | 0 | 0 | 0.0 |  |

Output:

```text
{'entries': 51, 'total_hits': Decimal('103'), 'expired': 0}
```

```python
display(cache.backend.execute(
    f"SELECT metadata->>'intent_id' AS intent_id, question, left(answer, 160) AS answer "
    f"FROM {cfg.qualified_table} WHERE model = %s AND prompt_version = %s ORDER BY 1",
    [scope["model"], scope["prompt_version"]],
))
```

Output:

| answer | intent_id | question |
|---|---|---|
| An account is usually locked or frozen because of a verification or security review. Follow the instructions in the in-app notice, or reach out via Profile > Su | account_frozen | Why is my account locked or frozen? |
| Your account and routing numbers are under Home > Account details. You can give these to your employer for direct deposit, or send the pre-filled form from Home | account_number_routing | Where do I find my account and routing number? |
| Go to Home > Add money. You have a few options: linked bank transfer (free, 1-3 business days), direct deposit, mobile check deposit (free in 1-5 business days  | add_money | How do I add money to my balance? |
| Your ATM withdrawal limit is $1,000 per day. Keep in mind there's no fee at in-network ATMs (find them under Card > Find ATMs), while out-of-network withdrawals | atm_limits | What are the ATM withdrawal limits? |
| Tap the Card tab and select **Find ATMs** to locate in-network ATMs, which are free. Using an out-of-network ATM costs $2.50 plus the ATM owner's fee. Note your | atm_locator | How do I find a free ATM? |
| You can enable Face ID or fingerprint login under Profile > Settings > Security. Just toggle it on from there. | biometric_login | How do I enable Face ID or fingerprint login? |
| Personal Lux Pay accounts can't be used for business. You'd need a Lux Pay for Business account, which accepts payments for a 2.75% fee per payment received. | business_account | Can I accept payments for my business? |
| To buy Bitcoin, you'll need a verified account (complete it under Profile > Verify), which unlocks the Invest tab. From there you can buy or sell Bitcoin starti | buy_bitcoin | How do I buy Bitcoin in the app? |
| Head to the Invest tab, where you can buy stocks and ETFs starting at just $1 with fractional shares and no commission. Note that you'll need to complete identi | buy_stock | How do I buy stocks in the app? |
| Completed payments are instant and can't be cancelled—you'd need to ask the recipient to send it back. However, if the payment is still pending, you can cancel  | cancel_pending_payment | Can I cancel a payment I already sent? |
| To activate your new Lux Card, go to the **Card** tab and tap **Activate**. If it's a replacement, your virtual card works right away for online and mobile wall | card_activation | How do I activate my new card? |
| Common reasons a Lux Card gets declined include: low balance, a locked card, the wrong PIN, hitting a limit, or a suspected-fraud check. If it's a fraud check,  | card_declined | Why was my card declined? |
| Standard cash-out to your bank is free and takes 1-3 business days. If you need it faster, instant cash-out arrives right away for a 1.5% fee (minimum $0.25, ma | cash_out_timing | How long does it take to cash out to my bank? |
| Go to Profile > Linked accounts to add, change, or remove a bank. From there you can update your linked bank as needed. | change_linked_bank | How do I change my linked bank account? |
| To close your account, go to Profile > Settings > Close account. Before you can close it, you'll need to cash out your balance and sell any investments. Note th | close_account | How do I close my account? |
| Lux Pay's Credit Builder lets you move money into a secured account and spend with the Credit Builder card. Your on-time payments are reported to all three cred | credit_building | How does the credit-building feature work? |
| In the Invest tab, you can sell Bitcoin or withdraw it to an external wallet. When withdrawing, the network fee is shown before you send, so you can review it b | crypto_withdrawal | How do I withdraw Bitcoin to an external wallet? |
| Direct deposits are available as soon as Lux Pay receives them from your payer—and you can get paid up to 2 days early automatically (and free) when your employ | direct_deposit_timing | When will my direct deposit arrive? |
| Open the transaction in your Activity and tap **Report a problem** to start the dispute. For eligible card disputes, you'll typically get provisional credit wit | dispute_charge | How do I dispute a charge I don't recognize? |
| You can find your monthly statements as PDFs under Profile > Documents. Tax forms (1099-B, 1099-INT, 1099-K) are also there, available by mid-February. | download_statement | How do I download my account statement? |
| Lux Pay has no monthly, overdraft, or foreign transaction fees. The main fees are:  - **Cash-out:** Standard to your bank is free (1-3 business days); instant i | fees_overview | What fees does the app charge? |
| Lux Pay charges no foreign transaction fees, so you won't pay extra on purchases abroad. At ATMs, in-network ones are free, but out-of-network ATMs cost $2.50 p | foreign_transaction | Are there fees for using my card abroad? |
| You can lock your Lux Card instantly from the Card tab—just tap to lock it, and tap again to unlock whenever you're ready. This is a quick way to pause your car | freeze_card | How do I temporarily lock my card? |
| Boosts are instant discounts at selected merchants. You choose one at a time under Card > Boosts, and it automatically applies when you pay at checkout. | gift_card_boosts | How do instant discounts or boosts work? |
| Go to Card > Report lost or stolen. This instantly cancels the card, and a free replacement arrives in 5-7 business days. In the meantime, your new virtual card | lost_stolen_card | What do I do if my card is lost or stolen? |

_26 more rows not shown._

```python
cache.close()
```
