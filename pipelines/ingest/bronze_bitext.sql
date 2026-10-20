-- Public Bitext retail-banking dataset (CDLA-Sharing-1.0): in-domain banking questions.
CREATE OR REFRESH STREAMING TABLE bronze_bitext
COMMENT "Raw Bitext retail-banking chatbot dataset (public, CDLA-Sharing-1.0)."
AS SELECT
  *,
  _metadata.file_path AS source_file,
  current_timestamp() AS ingested_at
FROM STREAM read_files('${raw_path}/public/bitext/', format => 'parquet');
