"""Semantic cache demo app: ROI calculator, playground, and false-hit judge.

The cache logic is the repo's ``semantic_cache`` package, unchanged; this module only wires
it to HTTP. Runs as the app's service principal (Lakebase OAuth, serving endpoints, SQL warehouse).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import uuid
from contextlib import asynccontextmanager
from dataclasses import replace

from databricks.sdk import WorkspaceClient
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from semantic_cache import CacheConfig, SemanticCache, chat_generator

from .event_log import EventLog
from .judge import Judge
from .measured import Measured
from .settings import ROOT, Settings
from .warehouse import Warehouse

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app")

S = Settings()
STATE: dict = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    host = os.environ.get("DATABRICKS_HOST", "")
    if host and not host.startswith("http"):   # Lakebase OAuth needs a URL, Apps may inject a bare host
        os.environ["DATABRICKS_HOST"] = f"https://{host}"
    w = WorkspaceClient()
    system_prompt = (ROOT / "data" / "system_prompt.txt").read_text().strip()
    cfg = CacheConfig(
        lakebase_instance=S.lakebase_instance, backend=S.backend, pg_schema=S.pg_schema,
        embedding_endpoint=S.embedding_endpoint, similarity_threshold=S.threshold,
        host=os.environ.get("PGHOST"), client_id=os.environ.get("DATABRICKS_CLIENT_ID"),
    )
    cache = SemanticCache(cfg, workspace_client=w)
    wh = Warehouse(w, S.warehouse_id)
    generate = chat_generator(S.llm_endpoint, system_prompt=system_prompt, workspace_client=w, max_tokens=400)
    with open(ROOT / "data" / "question_bank.json") as f:
        bank = json.load(f)
    STATE.update(
        w=w, cache=cache, generate=generate, bank=bank,
        # Replayed eval traffic must not count as real hits on the seeded entries.
        replay_cache=SemanticCache(replace(cfg, track_hits=False), backend=cache.backend, workspace_client=w),
        # Same scope as 01_build_cache (model + prompt hash); tenant varies, see scopes().
        scope={"model": S.llm_endpoint, "prompt_version": hashlib.sha256(system_prompt.encode()).hexdigest()[:8]},
        events=EventLog(w, S.warehouse_id, S.table("cache_events"), backend=S.backend,
                        price_in_per_m=S.price_in_per_m, price_out_per_m=S.price_out_per_m),
        measured=Measured(wh, S),
    )
    STATE["judge"] = Judge(w, wh, S, generate, STATE["scope"]["prompt_version"])
    log.info("Ready: backend=%s table=%s scope=%s", S.backend, cfg.qualified_table, STATE["scope"])
    yield
    cache.close()


app = FastAPI(title="Lakebase semantic cache", lifespan=lifespan)


def scopes() -> tuple[dict, dict]:
    """Lookups search the seeded entries (tenant "") and the app's own; misses are written to the app's."""
    base = STATE["scope"]
    return {**base, "tenant": ["", S.app_tenant]}, {**base, "tenant": S.app_tenant}


@app.exception_handler(Exception)
async def errors(_, exc: Exception):
    log.exception("Request failed")
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})


# --- config / ROI --------------------------------------------------------------------
@app.get("/api/config")
def config():
    stats = STATE["cache"].stats()
    return {
        "backend": S.backend, "llm_endpoint": S.llm_endpoint, "embedding_endpoint": S.embedding_endpoint,
        "threshold": S.threshold, "scope": STATE["scope"], "app_tenant": S.app_tenant,
        "price_in_per_m": S.price_in_per_m, "price_out_per_m": S.price_out_per_m,
        "cache_table": STATE["cache"].cfg.qualified_table, "lakebase_instance": S.lakebase_instance,
        "entries": int(stats["entries"]), "total_hits": int(stats["total_hits"]),
    }


@app.get("/api/measured")
def measured(refresh: bool = False):
    return STATE["measured"].get(refresh)


# --- playground ----------------------------------------------------------------------
class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    threshold: float = Field(ge=0.3, le=0.99)
    write_back: bool = True


@app.post("/api/ask")
def ask(body: AskIn):
    lookup_scope, write_scope = scopes()
    res = STATE["cache"].get_or_generate(
        body.question.strip(), STATE["generate"], lookup_scope, threshold=body.threshold,
        write_back=body.write_back, write_scope=write_scope, metadata={"source": "app"})
    res.scope = write_scope   # the request's scope, for the event log
    STATE["events"].log([res], run_id=str(uuid.uuid4()), source="app")
    return res.to_dict()


def _bank_queries() -> list[dict]:
    out = []
    for i in STATE["bank"]["intents"]:
        if i["cacheable"]:
            out += [{"question": p, "expected_intent": i["intent_id"], "cacheable": True} for p in i["paraphrases"]]
        else:   # account-specific: any hit serves a generic, wrong answer
            out += [{"question": q, "expected_intent": None, "cacheable": False}
                    for q in [i["canonical_question"], *i["paraphrases"]]]
    return out


@app.get("/api/sample-question")
def sample_question():
    return random.choice(_bank_queries())


class ReplayIn(BaseModel):
    n: int = Field(ge=1, le=150)
    threshold: float = Field(ge=0.3, le=0.99)


@app.post("/api/replay")
def replay(body: ReplayIn):
    """Look up a random sample of the held-out labeled paraphrases (lookup only, no LLM calls),
    log them, and score them against their labels. Feeds the judge with labeled hits."""
    cache = STATE["replay_cache"]
    lookup_scope, write_scope = scopes()
    queries = random.sample(_bank_queries(), min(body.n, len(_bank_queries())))
    embeddings = cache.embed([q["question"] for q in queries])
    results, rows = [], []
    for q, emb in zip(queries, embeddings):
        r = cache.lookup(q["question"], lookup_scope, threshold=body.threshold, embedding=emb)
        r.scope = write_scope
        results.append(r)
        matched = (r.matched_metadata or {}).get("intent_id")
        rows.append({
            "question": q["question"], "hit": r.hit, "similarity": r.similarity,
            "matched_question": r.matched_question, "cacheable": q["cacheable"],
            "correct": q["cacheable"] and matched == q["expected_intent"], "lookup_ms": r.lookup_ms,
        })
    STATE["events"].log(results, run_id=str(uuid.uuid4()), source="app-replay",
                        attributes=[{"expected_intent": q["expected_intent"], "cacheable": q["cacheable"]}
                                    for q in queries])
    hits = [r for r in rows if r["hit"]]
    return {
        "n": len(rows), "hits": len(hits), "wrong_hits": sum(not r["correct"] for r in hits),
        "threshold": body.threshold, "rows": rows,
    }


# --- false-hit judge -----------------------------------------------------------------
class JudgeIn(BaseModel):
    n: int = Field(ge=1, le=50)
    sources: list[str] = ["app", "app-replay"]


@app.post("/api/judge/run")
def judge_run(body: JudgeIn):
    STATE["events"].flush()   # judge the hits just logged, too
    try:
        return {"job_id": STATE["judge"].start(body.n, body.sources)}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/api/judge/job/{job_id}")
def judge_job(job_id: str):
    job = STATE["judge"].job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job")
    return job


@app.get("/api/judge/results")
def judge_results():
    return STATE["judge"].summary()


# --- UI ------------------------------------------------------------------------------
static = ROOT / "server" / "static"
if static.is_dir():
    app.mount("/", StaticFiles(directory=static, html=True), name="ui")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("DATABRICKS_APP_PORT", 8000)))
