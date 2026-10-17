#!/usr/bin/env python3
"""Verify a built catalog, then atomically select it. Run locally, not via HTTP."""
import hashlib,json,os,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve();version=sys.argv[2]
if not version or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in version):raise SystemExit('Invalid version')
p=root/version;manifest=p/'manifest.json';raw=manifest.read_bytes();m=json.loads(raw)
assert m['schema_version']==1 and m['snapshot_id']==version
for f in m['files']:
 target=(p/f['path']).resolve()
 assert target.is_relative_to(p) and target.is_file() and target.stat().st_size==f['bytes'],f['path']
 assert hashlib.sha256(target.read_bytes()).hexdigest()==f['sha256'],f['path']
index=json.loads((p/'index.json').read_bytes());assert index['schema_version']==1 and index['snapshot_id']==version
assert len(index['models'])==index['model_count'] and len({m['id'] for m in index['models']})==index['model_count']
tmp=root/'current.json.new';tmp.write_text(json.dumps({'snapshot_id':version,'manifest_sha256':hashlib.sha256(raw).hexdigest()},separators=(',',':')));os.replace(tmp,root/'current.json');print('CATALOG_SELECTED',version,index['model_count'])
