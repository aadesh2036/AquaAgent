"""Parquet writer for the §7.5 tables (local path or s3://).

Implementation: docs/modules/02_DATA_GENERATION.md
"""

from __future__ import annotations


def write_tables(tables: dict, out_uri: str, shard: int) -> None:
    """Write each table to `<out_uri>/<table>/part-<shard>.parquet`; columns per models.TABLE_COLUMNS."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/02_DATA_GENERATION.md")
