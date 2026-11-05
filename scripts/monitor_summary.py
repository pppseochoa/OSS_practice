"""Always preserve observations, gaps and one-screen HTML, even after deployment failure."""
import html
import json
import statistics
import sys
from pathlib import Path
from datetime import datetime

folder=Path(sys.argv[1]);folder.mkdir(parents=True,exist_ok=True)
rows=[]
if (folder/'requests.jsonl').exists():
    for line in (folder/'requests.jsonl').read_text(encoding='utf-8').splitlines():
        try: rows.append(json.loads(line))
        except json.JSONDecodeError: pass
gaps=[r for r in rows if r.get('idle_since_previous_end_s') is not None and r['idle_since_previous_end_s']+r['response_ms']/1000>1.5]
success=sum(r['success'] for r in rows);failure=len(rows)-success
versions=[]
for r in rows:
    if not versions or versions[-1]['version']!=r['deployment_version']:
        versions.append({'time':r['start_utc'],'version':r['deployment_version'],'model':r.get('model_version')})
intervals=[r['start_interval_s'] for r in rows if r.get('start_interval_s') is not None]
idle=[r['idle_since_previous_end_s'] for r in rows if r.get('idle_since_previous_end_s') is not None]
post=[r for r in rows if r['phase']=='post-deploy']
post_seconds=(datetime.fromisoformat(post[-1]['end_utc'])-datetime.fromisoformat(post[0]['start_utc'])).total_seconds() if post else 0
result={'address':rows[0]['url'] if rows else 'http://127.0.0.1:8080/api/v1/predict',
 'start_utc':rows[0]['start_utc'] if rows else None,'end_utc':rows[-1]['end_utc'] if rows else None,
 'requests':len(rows),'success':success,'failure':failure,'case_id':rows[0]['case_id'] if rows else None,
 'start_interval_mean_s':statistics.mean(intervals) if intervals else None,'start_interval_max_s':max(intervals,default=0),
 'idle_mean_s':statistics.mean(idle) if idle else None,'max_idle_gap_s':max(idle,default=0),
 'max_record_gap_s':max((r['idle_since_previous_end_s']+r['response_ms']/1000 for r in rows if r.get('idle_since_previous_end_s') is not None),default=0),
 'response_max_ms':max((r['response_ms'] for r in rows),default=0),'unverified_gaps_over_1_5s':gaps,
 'versions':versions,'post_deploy_observed_s':post_seconds,
 'representative_responses':([rows[0]]+[r for r in rows if r['phase']=='deploying'][:1]+post[:1]+[rows[-1]]) if rows else [],
 'interpretation':('Observed requests all succeeded with >=30s post-deploy coverage; no claim about instants between requests.' if rows and failure==0 and post_seconds>=30 and (folder/'done').exists() else 'Failures, incomplete coverage or no observations: uninterrupted deployment NOT verified.'),
 'gap_policy':'Completion-log gaps >1.5s are UNVERIFIED intervals (includes waiting for response). All time outside this log window is unverified. Scheduling is response completion + 1s, not fixed start-to-start 1s.'}
card=Path('ml/model-card.json')
if card.exists(): result['model_comparison']=json.loads(card.read_text(encoding='utf-8'))
(folder/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
fmt=lambda value: '-' if value is None else f'{value:.3f}' if isinstance(value,float) else str(value)
lines=['# Deployment observation summary',f"Address: {result['address']}",f"UTC: {result['start_utc']} → {result['end_utc']}",
 f"Requests: {len(rows)} | success {success} | failure {failure}",
 f"Completion-to-start interval mean: {fmt(result['idle_mean_s'])}s | maximum recording gap: {fmt(result['max_record_gap_s'])}s",
 f"Start-to-start mean/max: {fmt(result['start_interval_mean_s'])}/{fmt(result['start_interval_max_s'])}s | max response: {fmt(result['response_max_ms'])}ms",
 f"Post-deploy observation: {post_seconds:.2f}s | unverified gaps (>1.5s): {len(gaps)}",result['interpretation'],result['gap_policy'],
 '## Version transitions']+[f"- {v['time']} {v['version']} / {v['model']}" for v in versions]
lines+=['## Representative responses']+[json.dumps(r,ensure_ascii=False) for r in result['representative_responses']]
lines+=['## Unverified gaps']+[f"- before {r['start_utc']}: {r['idle_since_previous_end_s']:.3f}s" for r in gaps]
(folder/'summary.md').write_text('\n\n'.join(lines),encoding='utf-8')
e=lambda value:html.escape(str(value))
cards=[('Requests',len(rows)),('Success / failure',f'{success} / {failure}'),('Max gap',fmt(result['max_record_gap_s'])+'s'),('Post-deploy',f'{post_seconds:.1f}s')]
table=''.join('<tr>'+''.join('<td>'+e(r.get(k,'-'))+'</td>' for k in ['phase','start_utc','http_status','response_ms','analysis_ok','deployment_version','salary_krw'])+'</tr>' for r in result['representative_responses'])
comparison=result.get('model_comparison',{}).get('final_test',{})
model_line=''
if comparison:
    model_line='<p>Fixed holdout 20 | MAE '+f"{comparison['baseline']['mae_krw']:,.0f} → {comparison['selected']['mae_krw']:,.0f} KRW"+' | RMSE '+f"{comparison['baseline']['rmse_krw']:,.0f} → {comparison['selected']['rmse_krw']:,.0f} KRW"+'</p>'
content=f'''<!doctype html><meta charset="utf-8"><title>KBO deployment observation</title><style>
*{{box-sizing:border-box}}body{{font:15px Arial,sans-serif;background:#eef3f6;color:#163042;margin:0;padding:28px}}main{{max-width:1380px;margin:auto}}h1{{margin:0 0 10px}}.cards{{display:flex;gap:15px;margin:18px 0}}.card{{background:white;padding:18px;border-radius:10px;flex:1}}b{{font-size:30px;display:block}}table{{width:100%;border-collapse:collapse;background:white;font-size:12px;table-layout:fixed}}td,th{{padding:10px;border-bottom:1px solid #dde3e8;overflow-wrap:anywhere}}.note{{background:white;padding:16px;margin:14px 0;border-left:5px solid #e99839}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:14px;font-size:12px}}small{{color:#426079}}</style><main>
<h1>KBO model deployment · observation report</h1><small>{e(result['address'])}<br>{e(result['start_utc'])} → {e(result['end_utc'])} UTC</small>
{model_line}
<div class="cards">{''.join('<div class="card">'+e(k)+'<b>'+e(v)+'</b></div>' for k,v in cards)}</div>
<div class="note">{e(result['interpretation'])}<br>UNVERIFIED gaps &gt;1.5s: {len(gaps)}. Outside this window and between sampled requests, continuity is not guaranteed.</div>
<p>Completion + 1 second · actual idle mean {fmt(result['idle_mean_s'])}s · start interval mean/max {fmt(result['start_interval_mean_s'])}/{fmt(result['start_interval_max_s'])}s · max response {fmt(result['response_max_ms'])}ms</p>
<h3>Version transitions</h3><pre>{e(chr(10).join(v['time']+' '+v['version']+' / '+str(v['model']) for v in versions))}</pre>
<h3>Representative actual API responses</h3><table><tr>{''.join('<th>'+k+'</th>' for k in ['Phase','Start UTC','HTTP','Latency ms','Analysis OK','Deployment version','Salary KRW'])}</tr>{table}</table>
<p>Fixed case: {e(result['case_id'])}. Full request start/end timestamps, durations, versions and gap details: requests.jsonl / summary.json.</p></main>'''
(folder/'summary.html').write_text(content,encoding='utf-8')
print('\n'.join(lines))
