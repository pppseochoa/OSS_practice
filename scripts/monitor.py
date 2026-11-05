"""Independent, completion+1s sequential analysis-API observer. UTF-8 durable logs."""
import argparse
import json
from pathlib import Path
import sys
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

def utc(): return datetime.now(timezone.utc).isoformat(timespec='milliseconds')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--url',required=True);parser.add_argument('--directory',required=True);parser.add_argument('--case',required=True);args=parser.parse_args()
    folder=Path(args.directory);folder.mkdir(parents=True,exist_ok=True)
    payload=json.loads(Path(args.case).read_text(encoding='utf-8-sig'))
    body=json.dumps(payload['request']).encode()
    previous_end=previous_start=None
    post_start=None
    with (folder/'requests.jsonl').open('a',encoding='utf-8',buffering=1) as log:
        while True:
            if (folder/'stop.request').exists() and post_start is None: post_start=time.perf_counter()
            start=time.perf_counter();began=utc()
            row={'start_utc':began,'url':args.url,'case_id':payload['row_id'],
                 'idle_since_previous_end_s':None if previous_end is None else start-previous_end,
                 'start_interval_s':None if previous_start is None else start-previous_start}
            try:
                with urlopen(Request(args.url,data=body,headers={'Content-Type':'application/json'}),timeout=10) as response:
                    data=json.load(response);row['http_status']=response.status
                salary=data.get('suggested_salary_krw')
                row.update(analysis_ok=type(salary) is int and salary>0,
                    deployment_version=data.get('deployment_version','unknown-legacy'),model_version=data.get('model_version',data.get('model_status','unknown')),
                    salary_krw=salary)
            except Exception as error:
                row.update(http_status=getattr(error,'code',None),analysis_ok=False,error=str(error),deployment_version='unavailable',model_version='unavailable')
            end=time.perf_counter();row.update(end_utc=utc(),response_ms=(end-start)*1000)
            row['success']=row.get('http_status')==200 and row['analysis_ok']
            row['phase']='post-deploy' if post_start is not None else ('deploying' if (folder/'deploy.started').exists() else 'pre-deploy')
            encoded=json.dumps(row,ensure_ascii=False)
            log.write(encoded+'\n');log.flush()
            print(encoded,flush=True)
            if row['success']: (folder/'ready').touch()
            previous_start,previous_end=start,end
            if post_start is not None and end-post_start>=30: break
            time.sleep(1)
    (folder/'done').write_text(utc(),encoding='utf-8')

if __name__=='__main__': main()
