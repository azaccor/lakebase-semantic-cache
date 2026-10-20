"""Export readable evidence of a real run into evidence/: every notebook task's code and printed
output (decoded from the job run export), each pipeline update's per-table row counts and
expectation results, snapshots of the governed tables, and recorded responses from the deployed
app (including Ask Genie). Workspace-specific identifiers are replaced with placeholders.

    python scripts/export_evidence.py --profile <profile> --job-run <end-to-end run id> \\
        [--load-test-run <run id>] --app-url https://<app>.databricksapps.com \\
        --catalog <catalog> --schema semantic_cache --warehouse <warehouse id> --scrub <lakebase project>
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import ViewsToExport

ROOT = Path(__file__).resolve().parent.parent
ANSI = re.compile(r"\x1b\[[0-9;]*m")
MAX_ROWS, MAX_TEXT = 25, 6000

# Gold and evaluation tables to snapshot: (table, ORDER BY, row limit)
TABLES = [
    ("gold_cache_daily", "event_date DESC, requests DESC", 25),
    ("gold_judge_daily", "judged_date DESC", 25),
    ("gold_false_hit_monitor", "last_judged_ts DESC", 10),
    ("gold_threshold_curve", "backend, threshold", 20),
    ("gold_category_risk", "threshold, category", 40),
    ("silver_faq_intents", "category, intent_id", 60),
    ("eval_summary", "run_ts DESC", 5),
    ("load_test_latency", "run_id, size, clients", 40),
]


def ts(ms: int | None) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if ms else "—"


def md_table(columns: list[str], rows: list[list], limit: int = MAX_ROWS) -> str:
    def cell(v):
        if isinstance(v, float):
            v = round(v, 4)
        return str(v).replace("|", "\\|").replace("\n", " ")[:200] if v is not None else ""
    out = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    out += ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows[:limit]]
    if len(rows) > limit:
        out.append(f"\n_{len(rows) - limit} more rows not shown._")
    return "\n".join(out)


class Scrubber:
    def __init__(self, mapping: dict[str, str]):
        # Longest first, so a host is replaced before the shorter values it contains.
        self.mapping = sorted(((k, v) for k, v in mapping.items() if k), key=lambda kv: -len(kv[0]))

    def __call__(self, text: str) -> str:
        for k, v in self.mapping:
            text = text.replace(k, v)
        return re.sub(r"ep-[a-z]+-[a-z]+-[a-z0-9]{6,}", "<lakebase-endpoint>", text)

    def check(self, text: str, where: str) -> None:
        for k, _ in self.mapping:
            assert k not in text, f"unscrubbed value left in {where}"


# --- notebook task runs -------------------------------------------------------------------
def notebook_markdown(w: WorkspaceClient, task: dict) -> str:
    export = w.jobs.export_run(task["run_id"], views_to_export=ViewsToExport.CODE)
    html = export.views[0].content
    raw = re.search(r"__DATABRICKS_NOTEBOOK_MODEL = '([^']+)'", html).group(1)
    model = json.loads(urllib.parse.unquote(base64.b64decode(raw).decode()))
    out = []
    for c in sorted(model["commands"], key=lambda c: c.get("position", 0)):
        src = c["command"].strip()
        if src.startswith("%md"):
            out.append(src[3:].strip())
            continue
        out.append(f"```python\n{src}\n```")
        r = c.get("results") or {}
        items = r.get("data") if r.get("type") == "listResults" else [r] if r.get("type") else []
        for item in items or []:
            out.append(render_output(item))
        if c.get("error"):
            out.append(f"```text\n{ANSI.sub('', str(c['error']))[:MAX_TEXT]}\n```")
    return "\n\n".join(x for x in out if x)


def render_output(item: dict) -> str:
    kind, data = item.get("type"), item.get("data")
    if kind == "table" and isinstance(data, list):
        cols = [s["name"] for s in item.get("schema", [])] or [f"c{i}" for i in range(len(data[0]) if data else 0)]
        return "Output:\n\n" + md_table(cols, data)
    if kind == "mimeBundle" and isinstance(data, dict):
        text = data.get("text/plain")
        return f"Output:\n\n```text\n{text[:MAX_TEXT]}\n```" if text else "_(rich output: chart)_"
    if kind in ("ansi", "text") and data:
        text = ANSI.sub("", str(data)).strip()
        if text.startswith("Note: you may need to restart"):
            return ""
        return f"Output:\n\n```text\n{text[:MAX_TEXT]}\n```" if text else ""
    return ""


# --- pipeline task runs -------------------------------------------------------------------
def sql(w: WorkspaceClient, warehouse: str, statement: str) -> tuple[list[str], list[list]]:
    r = w.statement_execution.execute_statement(warehouse_id=warehouse, statement=statement, wait_timeout="50s")
    if not r.result or not r.manifest:
        raise RuntimeError(f"query did not return ({r.status.state if r.status else '?'}): {statement[:80]}")
    return [c.name for c in r.manifest.schema.columns], r.result.data_array or []


def pipeline_markdown(w: WorkspaceClient, task: dict, warehouse: str) -> str:
    """Rows written and expectation results per dataset, from the pipeline's event log (the
    event_log() table function: the list-events API omits these details), plus each table's rows."""
    pid = task["pipeline_task"]["pipeline_id"]
    start, end = task.get("start_time", 0), task.get("end_time") or 1 << 62
    update = next((u for u in w.pipelines.list_updates(pid).updates or []
                   if start - 60_000 <= (u.creation_time or 0) <= end), None)
    if not update:
        return "_No pipeline update found for this task._"
    _, flows = sql(w, warehouse, f"""
        SELECT origin.flow_name, details:flow_progress.metrics.num_output_rows,
               details:flow_progress.data_quality.dropped_records, details:flow_progress.data_quality.expectations
        FROM event_log('{pid}')
        WHERE event_type = 'flow_progress' AND origin.update_id = '{update.update_id}'
          AND details:flow_progress.status = 'COMPLETED'
        ORDER BY origin.flow_name""")
    counts = dict(sql(w, warehouse, " UNION ALL ".join(
        f"SELECT '{f[0]}', count(*) FROM {f[0]}" for f in flows))[1]) if flows else {}
    rows, expectations = [], []
    for name, written, dropped, exp in flows:
        rows.append([name.split(".")[-1], written if written is not None else "0 (no new input)", counts.get(name), dropped])
        expectations += [[x["dataset"].split(".")[-1], x["name"], x["passed_records"], x["failed_records"]]
                         for x in json.loads(exp or "[]")]
    info = w.pipelines.get_update(pid, update.update_id).update
    out = [f"Pipeline `{w.pipelines.get(pid).name}`, update `{update.update_id}`: **{info.state.value if info.state else '?'}**",
           "Streaming (bronze) tables only read new files, so a re-run writes 0 rows to them; materialized views recompute.",
           md_table(["dataset", "rows written this update", "rows in table", "rows dropped"], rows, 50)]
    if expectations:
        out += ["Data-quality expectations:", md_table(["dataset", "expectation", "passed", "failed"], expectations, 50)]
    return "\n\n".join(out)


# --- tables and app -----------------------------------------------------------------------
def table_snapshots(w: WorkspaceClient, warehouse: str, catalog: str, schema: str) -> str:
    out = []
    for name, order, limit in TABLES:
        cols, rows = sql(w, warehouse, f"SELECT * FROM {catalog}.{schema}.{name} ORDER BY {order} LIMIT {limit}")
        out.append(f"## {name}\n\n`SELECT * FROM {name} ORDER BY {order} LIMIT {limit}`\n\n" + md_table(cols, rows, limit))
    return "\n\n".join(out)


def app_calls(w: WorkspaceClient, app_url: str) -> dict[str, object]:
    headers = {**w.config.authenticate(), "Content-Type": "application/json"}
    get = lambda p: requests.get(app_url + p, headers=headers, timeout=120).json()
    post = lambda p, b: requests.post(app_url + p, headers=headers, json=b, timeout=300).json()
    measured = get("/api/measured")
    judge = get("/api/judge/results")
    judge["rows"] = judge.get("rows", [])[:10]
    return {
        "config": get("/api/config"),
        "measured": measured,
        "ask_cached_paraphrase": post("/api/ask", {"question": "I forgot my PIN, how can I change it?", "threshold": 0.75, "write_back": False}),
        "ask_false_hit_example": post("/api/ask", {"question": "How do I reset my password?", "threshold": 0.75, "write_back": False}),
        "replay_50_at_0.75": {k: v for k, v in post("/api/replay", {"n": 50, "threshold": 0.75}).items() if k != "rows"},
        "judge_results": judge,
        "genie_ask": post("/api/genie/ask", {"question": "What was our deflection rate and cost per question last week?"}),
        "genie_monitor": post("/api/genie/ask", {"question": "Is the false-hit monitor OK right now?"}),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--job-run", type=int, required=True)
    ap.add_argument("--load-test-run", type=int)
    ap.add_argument("--app-url", required=True)
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", default="semantic_cache")
    ap.add_argument("--warehouse", required=True)
    ap.add_argument("--scrub", action="append", default=[], help="extra value to replace with <redacted>")
    ap.add_argument("--out", default=str(ROOT / "evidence"))
    a = ap.parse_args()

    w = WorkspaceClient(profile=a.profile)
    me = w.current_user.me().user_name
    app_host = urllib.parse.urlparse(a.app_url).netloc
    app = next((x for x in w.apps.list() if x.url and app_host in x.url), None)
    scrub = Scrubber({
        urllib.parse.urlparse(w.config.host).netloc: "<workspace-host>", str(w.get_workspace_id()): "<workspace-id>",
        app_host: "<app-host>", me: "<user>", me.split("@")[0]: "<user>", a.catalog: "<catalog>",
        a.warehouse: "<warehouse-id>", **({app.service_principal_client_id: "<app-service-principal>"} if app else {}),
        **{v: "<redacted>" for v in a.scrub},
    })
    out = Path(a.out)
    (out / "runs").mkdir(parents=True, exist_ok=True)
    files: dict[Path, str] = {}

    index = ["# Run evidence", "",
             f"Exported {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} by `scripts/export_evidence.py` from real runs. "
             "Workspace identifiers are replaced with placeholders.", ""]
    for label, run_id in [("End-to-end job", a.job_run), ("Load test job", a.load_test_run)]:
        if not run_id:
            continue
        run = w.jobs.get_run(run_id).as_dict()
        state = run.get("state", {})
        index += [f"## {label}: `{run['run_name']}` (run {run_id})", "",
                  f"Result: **{state.get('result_state', state.get('life_cycle_state'))}**, started {ts(run.get('start_time'))}.", "",
                  "| task | result | started | duration | evidence |", "|---|---|---|---|---|"]
        for t in sorted(run["tasks"], key=lambda t: t.get("start_time") or 0):
            key, st = t["task_key"], t.get("state", {})
            if st.get("result_state") != "SUCCESS" and any(
                    x["task_key"] == key and x.get("state", {}).get("result_state") == "SUCCESS" and x["run_id"] != t["run_id"]
                    for x in run["tasks"]):
                index.append(f"| {key} | {st.get('result_state')} (retried) | {ts(t.get('start_time'))} | | |")
                continue
            path = out / "runs" / f"{key}.md"
            body = pipeline_markdown(w, t, a.warehouse) if "pipeline_task" in t else notebook_markdown(w, t)
            files[path] = f"# Task `{key}` (job run {run_id})\n\nResult: **{st.get('result_state')}**, " \
                          f"{ts(t.get('start_time'))} – {ts(t.get('end_time'))}.\n\n{body}\n"
            dur = ((t.get("end_time") or 0) - (t.get("start_time") or 0)) / 1000
            index.append(f"| {key} | {st.get('result_state')} | {ts(t.get('start_time'))} | {dur:.0f} s | [runs/{key}.md](runs/{key}.md) |")
        index.append("")

    files[out / "tables.md"] = "# Governed table snapshots\n\nRead through the SQL warehouse at export time.\n\n" + \
        table_snapshots(w, a.warehouse, a.catalog, a.schema) + "\n"
    files[out / "app_responses.json"] = json.dumps(app_calls(w, a.app_url), indent=2, default=str) + "\n"
    index += ["## Also", "", "- [tables.md](tables.md): snapshots of the gold, silver and evaluation tables.",
              "- [app_responses.json](app_responses.json): responses recorded from the deployed app: a cached paraphrase, "
              "a known false hit, a labeled replay, the judge's results, and two Ask Genie answers.", ""]
    files[out / "README.md"] = "\n".join(index)

    for path, text in files.items():
        text = scrub(text)
        scrub.check(text, str(path))
        path.write_text(text)
        print(f"wrote {path} ({len(text):,} bytes)")


if __name__ == "__main__":
    main()
