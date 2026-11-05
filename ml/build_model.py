"""Rebuild the already selected model using only the committed 80 training rows."""
import hashlib
import json
import joblib
import pandas as pd
from ml.experiment import ROOT, DATA, INPUTS, candidates
from ml.models import MODEL_PATH
from ml.collect_data import dataset_sha256

card=json.loads((ROOT/'ml'/'model-card.json').read_text(encoding='utf-8'))
assert dataset_sha256(DATA/'train.csv')==card['train_sha256']
train=pd.read_csv(DATA/'train.csv')
assert len(train)==80
model=candidates()[card['selected']]
model.fit(train[INPUTS],train.next_salary_krw)
MODEL_PATH.parent.mkdir(parents=True,exist_ok=True)
joblib.dump({'status':'trained','version':card['model_version'],'features':INPUTS,'pipeline':model,'train_sha256':card['train_sha256'],'selected':card['selected']},MODEL_PATH)
print('Built selected model from 80 train-only rows:',card['model_version'])
