"""Source-byte identity and exact raw-to-processed relational lineage."""
import hashlib
import json
import os
from pathlib import Path


def verify_raw(raw):
    from src.download import TABLES, validate
    manifest = json.loads((raw / 'pull_manifest.json').read_text(encoding='utf-8'))
    expected = {f"tb-{spec['id']}.json" for spec in TABLES}
    if set(manifest['files']) != expected:
        raise ValueError('source manifest file coverage mismatch')
    for spec in TABLES:
        name = f"tb-{spec['id']}.json"
        data = (raw / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest['files'][name]['sha256']:
            raise ValueError(f'source manifest hash identity mismatch: {name}')
        _, problems = validate(data, spec)
        if problems:
            raise ValueError(f'source structure invalid: {name}: {problems}')


def verify_processed(root):
    import duckdb
    verify_raw(root / 'data/raw')
    cwd = Path.cwd()
    try:
        os.chdir(root)
        with duckdb.connect() as con:
            con.execute((root / 'sql/01_staging.sql').read_text(encoding='utf-8'))
            for table in ('monthly', 'quarterly'):
                con.read_parquet(str(root / f'data/processed/{table}.parquet')).create_view('saved')
                difference = con.sql(f'SELECT count(*) FROM ((SELECT * FROM {table} EXCEPT ALL SELECT * FROM saved) '
                                     f'UNION ALL (SELECT * FROM saved EXCEPT ALL SELECT * FROM {table}))').fetchone()[0]
                if difference:
                    raise ValueError(f'source/processed generation lineage mismatch: {table}; rerun build_dataset')
                con.execute('DROP VIEW saved')
    finally:
        os.chdir(cwd)
