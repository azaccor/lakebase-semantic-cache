-- Public GooAQ question/answer pairs (Apache-2.0): real search questions.
CREATE OR REFRESH STREAMING TABLE bronze_gooaq
COMMENT "Raw GooAQ search question/answer pairs (public, Apache-2.0)."
AS SELECT
  *,
  _metadata.file_path AS source_file,
  current_timestamp() AS ingested_at
FROM STREAM read_files('${raw_path}/public/gooaq/', format => 'parquet');
