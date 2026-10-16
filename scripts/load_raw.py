"""
Load nightly clinic export files into the DuckDB warehouse's `raw` schema.

Design choices (each one is an interview talking point):

1. Raw stays raw. Every column is loaded as text, exactly as the clinic sent it.
   Cleaning happens later in dbt, so we can always reprocess from the original.
2. Every row carries lineage: which file it came from and when it was loaded.
3. Loads are idempotent. A manifest table records each file's content hash, so
   re-running the loader never double-loads a file. A re-sent file with a new
   name but identical content is detected and skipped.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "data" / "clinic_exports"
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"

# system folder -> (file pattern, delimiter)
SYSTEMS = {
    "system_a": ("*.csv", ","),
    "system_b": ("*.csv", ","),
    "system_c": ("*.txt", "|"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def setup(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("create schema if not exists raw")
    con.execute(
        """
        create table if not exists raw.load_manifest (
            file_name   varchar,
            system      varchar,
            file_hash   varchar,
            row_count   integer,
            status      varchar,   -- 'loaded' or 'skipped_duplicate_content'
            loaded_at   timestamp
        )
        """
    )


def load_file(con, system: str, path: Path, sep: str) -> str:
    file_hash = sha256(path)
    same_file = con.execute(
        "select status from raw.load_manifest where file_name = ? and file_hash = ?",
        [path.name, file_hash],
    ).fetchone()
    if same_file:
        # Seen this exact file before (loaded, or already skipped as a re-send).
        return "already_loaded" if same_file[0] == "loaded" else "already_skipped"
    seen = con.execute(
        "select file_name from raw.load_manifest where file_hash = ? and status = 'loaded'",
        [file_hash],
    ).fetchone()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if seen:
        # Same bytes, different name: a re-sent file. Record it, don't load it.
        con.execute(
            "insert into raw.load_manifest values (?, ?, ?, 0, 'skipped_duplicate_content', ?)",
            [path.name, system, file_hash, now],
        )
        return "skipped_duplicate_content"

    table = f"raw.{system}_appointments"
    select = f"""
        select *, ? as _source_file, ? as _loaded_at
        from read_csv(?, delim = ?, header = true, all_varchar = true)
    """
    params = [path.name, now, str(path), sep]
    exists = con.execute(
        "select count(*) from information_schema.tables where table_schema='raw' and table_name=?",
        [f"{system}_appointments"],
    ).fetchone()[0]
    if exists:
        con.execute(f"insert into {table} by name {select}", params)
    else:
        con.execute(f"create table {table} as {select}", params)
    rows = con.execute(
        f"select count(*) from {table} where _source_file = ?", [path.name]
    ).fetchone()[0]
    con.execute(
        "insert into raw.load_manifest values (?, ?, ?, ?, 'loaded', ?)",
        [path.name, system, file_hash, rows, now],
    )
    return "loaded"


def main() -> None:
    if not EXPORTS.exists():
        raise SystemExit("No clinic exports found. Run: python run.py simulate")
    con = duckdb.connect(str(WAREHOUSE))
    setup(con)
    counts: dict[str, int] = {}
    for system, (pattern, sep) in SYSTEMS.items():
        for path in sorted((EXPORTS / system).glob(pattern)):
            result = load_file(con, system, path, sep)
            counts[result] = counts.get(result, 0) + 1
            if result == "skipped_duplicate_content":
                print(f"  skipped re-sent file: {system}/{path.name}")
    print("files:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    for system in SYSTEMS:
        n = con.execute(f"select count(*) from raw.{system}_appointments").fetchone()[0]
        print(f"raw.{system}_appointments: {n:,} rows")
    con.close()


if __name__ == "__main__":
    main()
