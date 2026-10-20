# Task `land_raw` (job run 32232528631469)

Result: **SUCCESS**, 2026-10-20 00:59:13 UTC – 2026-10-20 00:59:49 UTC.

# 00a · Land raw files

Puts the raw inputs into a Unity Catalog Volume, one folder per source, where the
`semantic_cache_ingest` Lakeflow pipeline picks them up with Auto Loader (`read_files`):

| Folder | File | What | License |
|---|---|---|---|
| `question_bank/` | `question_bank.json` | Synthetic Lux Pay support FAQs, labeled paraphrases and account-specific probes (from this repo) | n/a |
| `public/bitext/` | `bitext.parquet` | [Bitext retail banking](https://huggingface.co/datasets/bitext/Bitext-retail-banking-llm-chatbot-training-dataset): in-domain banking questions, ~25K | CDLA-Sharing-1.0 |
| `public/gooaq/` | `gooaq_*.parquet` | [GooAQ](https://github.com/allenai/gooaq) ([HF mirror](https://huggingface.co/datasets/sentence-transformers/gooaq)): real search questions, ~3M | Apache-2.0 |

Re-running is safe: a file is only copied or downloaded if it isn't there yet. A changed
question bank is written under a new name, so the pipeline ingests it as a new file.

```python
dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "semantic_cache")

catalog, schema = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
raw_dir = f"/Volumes/{catalog}/{schema}/raw"
```

```python
import hashlib, os, shutil, requests

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.raw")
for d in ("question_bank", "public/bitext", "public/gooaq"):
    os.makedirs(f"{raw_dir}/{d}", exist_ok=True)

# The question bank, named by content hash: a changed bank is a new file for Auto Loader.
with open("../data/question_bank.json", "rb") as f:
    bank = f.read()
bank_path = f"{raw_dir}/question_bank/question_bank_{hashlib.sha256(bank).hexdigest()[:8]}.json"
if not os.path.exists(bank_path):
    with open(bank_path, "wb") as f:
        f.write(bank)
print("question bank:", bank_path)
```

Output:

```text
question bank: /Volumes/<catalog>/semantic_cache/raw/question_bank/question_bank_311108ac.json
```

```python
PUBLIC = {
    "public/bitext/bitext.parquet": "https://huggingface.co/api/datasets/bitext/Bitext-retail-banking-llm-chatbot-training-dataset/parquet/default/train/0.parquet",
    "public/gooaq/gooaq_0.parquet": "https://huggingface.co/api/datasets/sentence-transformers/gooaq/parquet/pair/train/0.parquet",
    "public/gooaq/gooaq_1.parquet": "https://huggingface.co/api/datasets/sentence-transformers/gooaq/parquet/pair/train/1.parquet",
}
for rel, url in PUBLIC.items():
    path = f"{raw_dir}/{rel}"
    if os.path.exists(path):
        print(f"present     {rel}")
        continue
    legacy = f"{raw_dir}/{os.path.basename(rel)}"   # where earlier versions of this repo downloaded it
    if os.path.exists(legacy):
        shutil.copyfile(legacy, path)
        print(f"copied      {rel}")
        continue
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    print(f"downloaded  {rel}: {os.path.getsize(path) / 1e6:.0f} MB")
```

Output:

```text
present     public/bitext/bitext.parquet
present     public/gooaq/gooaq_0.parquet
present     public/gooaq/gooaq_1.parquet
```

```python
display(spark.createDataFrame(
    [(root.replace(raw_dir, ""), name, os.path.getsize(os.path.join(root, name)))
     for root, _, files in os.walk(raw_dir) if "/question_bank" in root or "/public" in root for name in files],
    "folder string, file string, bytes long"))
```

Output:

| folder | file | bytes |
|---|---|---|
| /question_bank | question_bank_311108ac.json | 30854 |
| /public/bitext | bitext.parquet | 7871042 |
| /public/gooaq | gooaq_0.parquet | 306606760 |
| /public/gooaq | gooaq_1.parquet | 306642172 |
