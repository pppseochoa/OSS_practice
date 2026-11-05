"""Create a fixed holdout request outside Git; never used by model fitting."""
import json
import hashlib
import sys
from pathlib import Path
import pandas as pd
from ml.collect_data import FEATURES, main as collect, ROOT, dataset_sha256

test=ROOT/'ml'/'datasets'/'test.csv'
if not test.exists(): collect()
manifest=json.loads((ROOT/'ml'/'datasets'/'manifest.json').read_text(encoding='utf-8'))
assert dataset_sha256(test)==manifest['sha256']['test']
row=pd.read_csv(test).iloc[0]
payload={'row_id':row.row_id,'request':{'player_type':row.player_type,'stats':{k:float(row[k]) for k in FEATURES}}}
Path(sys.argv[1]).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
