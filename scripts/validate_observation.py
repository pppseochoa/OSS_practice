"""A green job requires complete coverage, not just a live container."""
import json
import sys
from pathlib import Path

folder=Path(sys.argv[1])
summary=json.loads((folder/'summary.json').read_text(encoding='utf-8'))
assert (folder/'done').exists(), 'Observer terminated unexpectedly; missing interval is UNVERIFIED'
assert summary['requests']>0 and summary['failure']==0, 'Request failures or no observations'
assert summary['post_deploy_observed_s']>=30, 'Less than 30 seconds post-deploy coverage'
if len(sys.argv)>2:
    assert sys.argv[2] in [v['version'] for v in summary['versions']], 'New deployment version never observed'
print('Complete independent observation and version verification: PASS')
