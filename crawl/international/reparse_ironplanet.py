"""Refresh only IronPlanet model fields from stored source JSON; no HTTP calls."""
import argparse
import json
from pathlib import Path

from crawl.common import load_mysql_config, mysql_connect, record_model_norm
from crawl.international.parsers import parse_listing_payload


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup',type=Path,required=True)
    args=parser.parse_args()
    config=load_mysql_config()
    with mysql_connect(config,config.database) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id,manufacturer,model_name,model_norm,raw_json FROM listings WHERE source_site='IronPlanet'")
            rows=cursor.fetchall()
        # Exclusive creation prevents accidental overwrite of an earlier backup.
        with args.backup.open('x',encoding='utf-8') as backup:
            json.dump(rows,backup,ensure_ascii=False,default=str)
        updates=[]
        for row in rows:
            raw=json.loads(row['raw_json'] or '{}')
            source=raw.get('source') or {}
            if not source.get('equipId'):
                continue
            parsed=parse_listing_payload('ironplanet',source)
            updates.append((parsed['manufacturer'],parsed['model_name'],record_model_norm(parsed),row['id']))
        conn.begin()
        try:
            with conn.cursor() as cursor:
                cursor.executemany("UPDATE listings SET manufacturer=%s,model_name=%s,model_norm=%s WHERE id=%s AND source_site='IronPlanet'",updates)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    print(json.dumps({'source':'IronPlanet','updated':len(updates),'httpRequests':0,'backup':str(args.backup)}))


if __name__=='__main__':main()
