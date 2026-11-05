"""Reproduce a 100-player, 2017 -> 2018 factual web dataset. No synthetic labels."""
import csv
import hashlib
import io
import json
from pathlib import Path
from urllib.request import urlopen
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent.parent
SOURCE_COMMIT = '1492f1df10f1983964712771abb336fb16e0f2eb'
BASE = f'https://raw.githubusercontent.com/yoonkt200/python-data-analysis/{SOURCE_COMMIT}/data/'
FEATURES = ['games', 'plate_appearances', 'batting_average', 'home_runs', 'rbi', 'stolen_bases', 'games_pitched', 'innings_pitched', 'wins', 'saves', 'era', 'strikeouts']

def dataset_sha256(path):
    # CSV values are invariant under Git's CRLF/LF conversion. Canonical CRLF
    # preserves the originally evaluated snapshot hash on Windows and Linux.
    canonical=Path(path).read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
    return hashlib.sha256(canonical).hexdigest()

def main():
    selected, sources = [], []
    for kind, file in [('batter', 'batter_stats_2017.csv'), ('pitcher', 'picher_stats_2017.csv')]:
        raw = urlopen(BASE + file, timeout=60).read()
        sources.append({'url': BASE + file, 'sha256': hashlib.sha256(raw).hexdigest()})
        rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
        candidates = []
        for r in rows:
            row = dict.fromkeys(FEATURES, 0)
            row.update(player_type=kind, player_name=r['선수명'], team=r['팀명'], season=2017,
                       next_salary_krw=int(float(r['연봉(2018)']) * 10000), source_url=BASE+file)
            if kind == 'batter':
                for dst, src in zip(FEATURES[:6], ['경기','타석','타율','홈런','타점','도루']): row[dst] = float(r[src])
            else:
                innings = float(r['이닝'])
                # STATIZ baseball notation .1/.2 represents 1/3 and 2/3 inning.
                whole = int(innings); fraction = round((innings-whole)*10)
                innings = whole + fraction/3 if fraction in (1,2) else innings
                for dst,src in [('games_pitched','경기'),('wins','승'),('saves','세'),('era','ERA')]: row[dst]=float(r[src])
                row['innings_pitched']=innings
                # Source provides rounded K/9, not exact strikeout count. Marked derivation.
                row['strikeouts']=round(float(r['삼진/9'])*innings/9)
            row['row_id']=hashlib.sha256(f"{kind}:{r['선수명']}:{r['팀명']}:2017".encode()).hexdigest()[:16]
            if row['next_salary_krw'] > 0: candidates.append(row)
        # Hash ordering avoids ordering by WAR/salary and is independent of labels.
        unique = {}
        for row in candidates: unique.setdefault(row['row_id'], row)
        selected += sorted(unique.values(), key=lambda r: hashlib.sha256(('selection-v1:'+r['row_id']).encode()).hexdigest())[:50]
    assert len(selected)==100 and len({r['row_id'] for r in selected})==100
    train, test = train_test_split(selected, test_size=20, random_state=42, stratify=[r['player_type'] for r in selected])
    output = ROOT/'ml'/'datasets'; output.mkdir(exist_ok=True)
    fields=['row_id','player_type','player_name','team','season']+FEATURES+['next_salary_krw','source_url']
    hashes={}
    for split, rows in [('train',train),('test',test)]:
        path=output/f'{split}.csv'
        with path.open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
        hashes[split]=dataset_sha256(path)
    manifest={'source_commit':SOURCE_COMMIT,'sources':sources,'stats_season':2017,'target_season':2018,'salary_unit':'KRW (source ten-thousand KRW x 10000)',
              'selection':'hash order, 50 batters and 50 pitchers; no label ranking','split_seed':42,'train_count':80,'test_count':20,
              'sha256':hashes,'train_ids':[r['row_id'] for r in train],'test_ids':[r['row_id'] for r in test],
              'pitcher_strikeouts':'derived by rounding source K/9 * fractional innings / 9; not an independently collected exact count',
              'limitations':'Historical STATIZ-derived educational snapshot, not current salaries or an independent KBO audit; contract/FA/age/previous salary intentionally unavailable to existing UI.'}
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Collected 100 real rows. Train=80 (40+40), sealed final test=20 (10+10).')
    print(json.dumps(hashes))

if __name__=='__main__': main()
