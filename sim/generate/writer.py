"""Deterministic Parquet writer/reader for the §7.5 tables (local path or s3://).

Same code path for local and S3: `fsspec.core.url_to_fs` (s3fs under the hood, credentials from the
default chain = ECS task role in AWS). No boto3 anywhere under sim/.

Determinism: explicit Arrow schema per column, no pandas index, pandas/schema metadata stripped,
zstd (fixed level), fixed row order is the caller's job (sim, time, id).

Implementation: docs/modules/02_DATA_GENERATION.md
"""

from __future__ import annotations

import posixpath

import fsspec
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from shared.contracts.models import TABLE_COLUMNS

ZSTD_LEVEL = 3

_STR = pa.string()
_COLUMN_TYPES: dict[str, pa.DataType] = {}
for _c in (
    "simulation_id dataset_version network_id sensor_layout_id scenario_type fault_type location_kind "
    "location_id zone_id severity_bucket config_hash generator_version spec_json split node_id node_type "
    "link_id link_type status tank_id pump_id sensor_id source_kind source_id measurement "
    "sensor_fault_kind check detail element_kind element_id start_node end_node features_json"
).split():
    _COLUMN_TYPES[_c] = _STR
for _c in "is_anomalous has_sensor_fault valid is_sensor passed".split():
    _COLUMN_TYPES[_c] = pa.bool_()
for _c in "sim_time_s seed fault_start_s fault_end_s hop_to_nearest_sensor time_of_day_s pump_status".split():
    _COLUMN_TYPES[_c] = pa.int64()


def _type(col: str) -> pa.DataType:
    return _COLUMN_TYPES.get(col, pa.float64())


def to_arrow(df: pd.DataFrame, table: str) -> pa.Table:
    """DataFrame -> Arrow with the contract column order/types, metadata stripped."""
    allowed = list(TABLE_COLUMNS[table])
    cols = list(df.columns)
    if [c for c in allowed if c in cols] != cols:
        raise ValueError(f"{table}: columns {cols} are not an in-order subset of {allowed}")
    schema = pa.schema([(c, _type(c)) for c in cols])
    return pa.Table.from_pandas(df, schema=schema, preserve_index=False).replace_schema_metadata(None)


def join(uri: str, *parts: str) -> str:
    return uri.rstrip("/") + "/" + "/".join(p.strip("/") for p in parts)


def _fs(uri: str):
    return fsspec.core.url_to_fs(uri)


def _write_arrow(table: pa.Table, uri: str) -> str:
    fs, path = _fs(uri)
    if "file" in fs.protocol or fs.protocol == "file":
        fs.makedirs(posixpath.dirname(path), exist_ok=True)
    with fs.open(path, "wb") as f:
        pq.write_table(
            table,
            f,
            compression="zstd",
            compression_level=ZSTD_LEVEL,
            use_dictionary=True,
            write_statistics=True,
            version="2.6",
            data_page_version="1.0",
        )
    return uri


def write_table(df: pd.DataFrame, table: str, uri: str) -> str:
    """Write one table to the exact parquet object `uri`."""
    return _write_arrow(to_arrow(df, table), uri)


def write_shard(tables: dict[str, pd.DataFrame], out_uri: str, shard: int) -> list[str]:
    """`<out>/<table>/part-<shard:03d>.parquet` for each table. Returns the written URIs."""
    return [write_table(df, name, join(out_uri, name, f"part-{shard:03d}.parquet")) for name, df in tables.items()]


# kept for the original stub name
def write_tables(tables: dict[str, pd.DataFrame], out_uri: str, shard: int) -> list[str]:
    return write_shard(tables, out_uri, shard)


def read_table(uri: str) -> pd.DataFrame:
    fs, path = _fs(uri)
    with fs.open(path, "rb") as f:
        return pq.read_table(f).to_pandas()


def list_parts(root_uri: str, pattern: str) -> list[str]:
    """Sorted URIs under `root_uri` matching the glob `pattern` (local or s3://)."""
    fs, path = _fs(root_uri)
    hits = sorted(fs.glob(posixpath.join(path.rstrip("/"), pattern)))
    proto = root_uri.split("://", 1)[0] + "://" if "://" in root_uri else ""
    return [proto + h if proto else h for h in hits]


def write_text(text: str, uri: str) -> str:
    fs, path = _fs(uri)
    if "file" in fs.protocol or fs.protocol == "file":
        fs.makedirs(posixpath.dirname(path), exist_ok=True)
    with fs.open(path, "wb") as f:
        f.write(text.encode())
    return uri


def concat(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """pd.concat without the all-NA-column dtype FutureWarning (dtypes are re-fixed by the Arrow schema)."""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        return pd.concat(frames, ignore_index=True)
