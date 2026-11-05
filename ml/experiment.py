"""Exactly two predefined small candidates. Selection uses train-only CV."""
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler, FunctionTransformer
from ml.collect_data import FEATURES
from ml.models import MODEL_PATH, UntrainedSalaryModel

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'ml'/'datasets'
INPUTS=['player_type']+FEATURES

def candidates():
    numeric=Pipeline([('impute',SimpleImputer(strategy='median')),('log_stats',FunctionTransformer(np.log1p)),('scale',StandardScaler())])
    prep=ColumnTransformer([('numbers',numeric,FEATURES),('type',OneHotEncoder(handle_unknown='ignore',sparse_output=False),['player_type'])])
    return {
      'attempt_1_log_ridge':TransformedTargetRegressor(regressor=Pipeline([('preprocess',prep),('regressor',Ridge(alpha=10))]),func=np.log1p,inverse_func=np.expm1),
      'attempt_2_small_extra_trees':Pipeline([('preprocess',prep),('regressor',ExtraTreesRegressor(n_estimators=64,max_depth=5,min_samples_leaf=3,random_state=42,n_jobs=1))])}

def metrics(y,p):
    p=np.maximum(1,np.rint(p))
    return {'mae_krw':float(mean_absolute_error(y,p)),'rmse_krw':float(np.sqrt(mean_squared_error(y,p))),'r2':float(r2_score(y,p))}

def fit_selected():
    # Never open test.csv here, including imputation/scaling/model selection.
    train=pd.read_csv(DATA/'train.csv')
    manifest=json.loads((DATA/'manifest.json').read_text(encoding='utf-8'))
    assert len(train)==80 and hashlib.sha256((DATA/'train.csv').read_bytes()).hexdigest()==manifest['sha256']['train']
    assert not set(train.row_id)&set(manifest['test_ids'])
    scores={}
    models=candidates()
    for name,model in models.items():
        losses=-cross_val_score(model,train[INPUTS],train.next_salary_krw,cv=KFold(5,shuffle=True,random_state=42),scoring='neg_mean_absolute_error')
        scores[name]={'cv_mae_krw':float(losses.mean()),'fold_mae_krw':losses.tolist()}
    selected=min(scores,key=lambda name:scores[name]['cv_mae_krw'])
    model=models[selected];model.fit(train[INPUTS],train.next_salary_krw)
    version='kbo-2017-v1-'+manifest['sha256']['train'][:12]
    MODEL_PATH.parent.mkdir(parents=True,exist_ok=True)
    joblib.dump({'status':'trained','version':version,'features':INPUTS,'pipeline':model,'train_sha256':manifest['sha256']['train'],'selected':selected},MODEL_PATH)
    card={'model_version':version,'selected':selected,'attempt_count':2,'selection_metric':'5-fold CV MAE on 80 training rows only','cv':scores,'train_sha256':manifest['sha256']['train'],'test_sha256':manifest['sha256']['test'],'train_count':80,'test_count':20}
    return card

def evaluate_once(card):
    # Final holdout is first opened AFTER candidate selection and final fit.
    test=pd.read_csv(DATA/'test.csv')
    assert len(test)==20 and hashlib.sha256((DATA/'test.csv').read_bytes()).hexdigest()==card['test_sha256']
    model=joblib.load(MODEL_PATH)
    before=np.array([UntrainedSalaryModel().predict(r.player_type,{k:r[k] for k in FEATURES}) for _,r in test.iterrows()])
    after=model['pipeline'].predict(test[INPUTS])
    card['final_test']={'baseline':metrics(test.next_salary_krw,before),'selected':metrics(test.next_salary_krw,after)}
    card['mae_improvement_percent']=100*(1-card['final_test']['selected']['mae_krw']/card['final_test']['baseline']['mae_krw'])
    errors=test[['row_id','player_name','player_type','next_salary_krw']].copy()
    errors['baseline_prediction']=np.rint(before).astype(int);errors['selected_prediction']=np.maximum(1,np.rint(after)).astype(int)
    errors['absolute_error']=(errors.next_salary_krw-errors.selected_prediction).abs()
    reports=ROOT/'reports';reports.mkdir(exist_ok=True)
    errors.sort_values('absolute_error',ascending=False).to_csv(reports/'holdout_errors.csv',index=False,encoding='utf-8')
    card['limitations']='20 holdout rows are a small historical sample; model selection never uses these scores; no additional tuning after holdout evaluation.'
    (ROOT/'ml'/'model-card.json').write_text(json.dumps(card,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(card,ensure_ascii=False,indent=2))

if __name__=='__main__':
    import sys
    card=fit_selected()
    if '--evaluate' in sys.argv: evaluate_once(card)
    else: print(json.dumps(card,indent=2))
