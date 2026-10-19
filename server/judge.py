"""Measured false-hit rate: sample cache hits the app served, regenerate a fresh answer to
the user's question with the LLM, and have an LLM judge decide whether the cached answer
correctly answers it. Results go to Delta (judge_results), next to cache_events.

Hits from the replay of labeled paraphrases also carry the ground-truth intent, so the
judge's verdicts can be checked against the labels (judge/label agreement)."""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

from .settings import Settings
from .warehouse import Warehouse, num

log = logging.getLogger(__name__)

JUDGE_COLUMNS = [
    ("event_key", "STRING"), ("judged_ts", "TIMESTAMP"), ("judge_model", "STRING"), ("judge_version", "STRING"),
    ("source", "STRING"),
    ("question", "STRING"), ("matched_question", "STRING"), ("similarity", "DOUBLE"), ("threshold", "DOUBLE"),
    ("cached_answer", "STRING"), ("fresh_answer", "STRING"), ("verdict", "STRING"), ("reason", "STRING"),
    ("expected_intent", "STRING"), ("matched_intent", "STRING"), ("label_correct", "BOOLEAN"),
    ("prompt_version", "STRING"),   # the cache scope's: re-seeding under a new system prompt starts over
]

JUDGE_PROMPT = """You are auditing a semantic cache in front of a customer-support assistant. The cache
served a stored answer, originally written for a similar question, instead of calling the model.

User's question:
{question}

Answer the cache served (written for: "{matched_question}"):
{cached_answer}

Reference answer, freshly generated for the user's question:
{fresh_answer}

Is the served answer a correct answer to the user's question? The reference is one acceptable
answer, not the only one: do not mark the served answer incorrect for different wording, a different
structure, or for leaving out details the reference happens to include. It is INCORRECT only if it
answers a different question than the one asked, does not address what the user actually asked, or
gives guidance that is wrong or would mislead this user.

Reply with JSON only, no other text before or after it:
{{"verdict": "correct" or "incorrect", "reason": "<one sentence>"}}"""

# Results are kept per judge prompt: changing the prompt starts a fresh measurement.
JUDGE_VERSION = hashlib.sha256(JUDGE_PROMPT.encode()).hexdigest()[:8]

# A hit's identity in cache_events (which has no id column): rows of one log call share
# run_id and event_ts, and a replay never repeats a question within a run. Each question is
# judged once per judge (model + prompt version) and cache prompt version, so repeats of a question don't weigh the rate twice.
EVENT_KEY = "sha2(concat_ws('|', e.run_id, cast(e.event_ts AS string), e.question), 256)"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


class Judge:
    def __init__(self, w, wh: Warehouse, settings: Settings, generate, prompt_version: str):
        self.w, self.wh, self.s, self.generate, self.prompt_version = w, wh, settings, generate, prompt_version
        self.table = settings.table("judge_results")
        self.jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        self.wh.query(f"CREATE TABLE IF NOT EXISTS {self.table} ("
                      + ", ".join(f"{c} {t}" for c, t in JUDGE_COLUMNS) + ")")
        have = {r["col_name"] for r in self.wh.query(f"DESCRIBE TABLE {self.table}")}
        if missing := [(c, t) for c, t in JUDGE_COLUMNS if c not in have]:   # a table from an older version
            self.wh.query(f"ALTER TABLE {self.table} ADD COLUMNS ("
                          + ", ".join(f"{c} {t}" for c, t in missing) + ")")

    # --- jobs ---------------------------------------------------------------------
    def start(self, n: int, sources: list[str]) -> str:
        with self._lock:
            if any(j["state"] == "running" for j in self.jobs.values()):
                raise RuntimeError("A judge run is already in progress")
            job_id = uuid.uuid4().hex[:12]
            self.jobs[job_id] = {"id": job_id, "state": "running", "total": None, "done": 0, "error": None}
        threading.Thread(target=self._run, args=(job_id, n, sources), daemon=True).start()
        return job_id

    def job(self, job_id: str) -> dict | None:
        return self.jobs.get(job_id)

    def _run(self, job_id: str, n: int, sources: list[str]) -> None:
        job = self.jobs[job_id]
        try:
            sample = self._sample(n, sources)
            job["total"] = len(sample)
            with ThreadPoolExecutor(max_workers=4) as pool:
                for _ in pool.map(self._judge_one, sample):
                    job["done"] += 1
            job["state"] = "done"
        except Exception as e:   # surfaced to the UI through the job status
            log.exception("Judge run failed")
            job.update(state="error", error=str(e))

    # --- steps --------------------------------------------------------------------
    def _sample(self, n: int, sources: list[str]) -> list[dict]:
        src = {f"src{i}": s for i, s in enumerate(sources)}
        return self.wh.query(
            f"""SELECT {EVENT_KEY} AS event_key, e.source, e.question, e.answer, e.matched_question,
                       e.similarity, e.threshold, e.attributes, e.matched_metadata
                FROM {self.s.table("cache_events")} e
                LEFT ANTI JOIN {self.table} j
                  ON j.question = e.question AND j.judge_model = :model AND j.judge_version = :version
                 AND j.prompt_version = :prompt_version
                 AND j.verdict IN ('correct', 'incorrect')   -- retry unparsed verdicts
                WHERE e.hit AND e.scope['model'] = :model AND e.scope['prompt_version'] = :prompt_version
                  AND e.source IN ({", ".join(":" + k for k in src)})
                QUALIFY row_number() OVER (PARTITION BY e.question ORDER BY e.event_ts DESC) = 1
                ORDER BY e.event_ts DESC LIMIT {int(n)}""",
            {"model": self.s.llm_endpoint, "version": JUDGE_VERSION, "prompt_version": self.prompt_version, **src})

    def _judge_one(self, e: dict) -> None:
        fresh = self.generate(e["question"])
        fresh_text = getattr(fresh, "text", fresh)
        resp = self.w.serving_endpoints.query(
            name=self.s.llm_endpoint, max_tokens=600,
            messages=[ChatMessage(role=ChatMessageRole.USER, content=JUDGE_PROMPT.format(
                question=e["question"], matched_question=e["matched_question"], cached_answer=e["answer"],
                fresh_answer=fresh_text))])
        verdict, reason = parse_verdict(resp.choices[0].message.content)

        attrs = json.loads(e["attributes"]) if e.get("attributes") else {}
        matched = (json.loads(e["matched_metadata"]) if e.get("matched_metadata") else {}).get("intent_id")
        label = None
        if "cacheable" in attrs:   # a labeled replay query
            label = bool(attrs["cacheable"]) and attrs.get("expected_intent") == matched
        row = {
            "event_key": e["event_key"], "judged_ts": datetime.now(timezone.utc).isoformat(),
            "judge_model": self.s.llm_endpoint, "judge_version": JUDGE_VERSION, "source": e["source"], "question": e["question"],
            "matched_question": e["matched_question"], "similarity": e["similarity"], "threshold": e["threshold"],
            "cached_answer": e["answer"], "fresh_answer": fresh_text, "verdict": verdict, "reason": reason,
            "expected_intent": attrs.get("expected_intent"), "matched_intent": matched,
            "label_correct": None if label is None else str(label).lower(), "prompt_version": self.prompt_version,
        }
        self.wh.query(
            f"INSERT INTO {self.table} ({', '.join(c for c, _ in JUDGE_COLUMNS)}) VALUES ("
            + ", ".join(f"CAST(:{c} AS {t})" for c, t in JUDGE_COLUMNS) + ")", row)

    # --- results ------------------------------------------------------------------
    def summary(self, limit: int = 100) -> dict:
        agg = self.wh.query(
            f"""SELECT count(*) AS n, count_if(verdict = 'incorrect') AS incorrect,
                       count(label_correct) AS labeled,
                       count_if(label_correct IS NOT NULL AND (verdict = 'correct') = label_correct) AS agree,
                       count_if(label_correct = false) AS label_incorrect, max(judged_ts) AS last_ts
                FROM {self.table} WHERE judge_model = :model AND judge_version = :version
                  AND prompt_version = :prompt_version
                  AND verdict IN ('correct', 'incorrect')""",
            {"model": self.s.llm_endpoint, "version": JUDGE_VERSION, "prompt_version": self.prompt_version})[0]
        rows = self.wh.query(
            f"""SELECT judged_ts, source, question, matched_question, similarity, threshold, cached_answer,
                       fresh_answer, verdict, reason, expected_intent, matched_intent, label_correct
                FROM {self.table} WHERE judge_model = :model AND judge_version = :version
                  AND prompt_version = :prompt_version
                ORDER BY judged_ts DESC LIMIT {int(limit)}""",
            {"model": self.s.llm_endpoint, "version": JUDGE_VERSION, "prompt_version": self.prompt_version})
        n, k = int(agg["n"]), int(agg["incorrect"])
        labeled = int(agg["labeled"])
        for r in rows:
            r["similarity"], r["threshold"] = num(r["similarity"]), num(r["threshold"])
            r["label_correct"] = None if r["label_correct"] is None else r["label_correct"] == "true"
        return {
            "source": self.table, "judge_model": self.s.llm_endpoint, "judge_version": JUDGE_VERSION, "prompt_version": self.prompt_version,
            "last_ts": agg["last_ts"],
            "judged": n, "incorrect": k, "false_hit_rate": k / n if n else None, "ci95": wilson(k, n),
            "labeled": labeled, "agreement": int(agg["agree"]) / labeled if labeled else None,
            "label_false_hit_rate": int(agg["label_incorrect"]) / labeled if labeled else None,
            "rows": rows,
        }


def parse_verdict(text: str) -> tuple[str, str]:
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        d = {}
    verdict = str(d.get("verdict", "")).strip().lower()
    if verdict not in ("correct", "incorrect"):
        return "unparsed", (text or "")[:300]
    return verdict, str(d.get("reason", ""))[:500]
