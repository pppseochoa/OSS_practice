# KBO 성적 기반 다음 시즌 연봉 예측

Django 웹 + FastAPI 분석 API입니다. 타자·투수 입력 화면과 `suggested_salary_krw` 응답을 유지합니다. 현재 모델은 2017년 성적에서 2018년 연봉을 예측하는 소규모 실험 모델이며, 최신 계약·FA·나이·부상·현재 물가를 반영하지 않습니다.

## 실제 데이터와 평가

- 출처: [저자가 공개한 STATIZ 기반 실습 원본](https://github.com/yoonkt200/python-data-analysis/tree/1492f1df10f1983964712771abb336fb16e0f2eb/data), `batter_stats_2017.csv`와 `picher_stats_2017.csv`.
- 원본 커밋 고정, 중복 선수/팀/유형 제거, 레이블과 무관한 해시 순서로 타자 50명·투수 50명을 선택합니다. 원본 연봉 단위 만원을 원으로 변환했습니다.
- 80건(타자40/투수40) 학습, 20건(타자10/투수10) 최종 테스트. seed=42, 행 ID와 SHA256은 `ml/datasets/manifest.json`에 고정됩니다.
- 투수 이닝 `.1/.2`는 각각 1/3·2/3으로 변환합니다. 원본에 정확한 탈삼진 수 대신 반올림된 K/9만 있어 `K/9 × 실제 이닝 / 9`를 반올림한 파생값을 사용합니다. 이는 독립 수집한 정확한 탈삼진 기록이 아닙니다.
- 현재 API로 입력할 수 없는 이전 연봉, WAR, 팀, 선수명, 2018년 연봉은 설명변수에서 제외했습니다. 원본은 역사적 2차 공개 자료이며 독립적인 KBO 공식 원장 대조를 완료한 데이터가 아닙니다.

개선 시도는 정확히 **두 개의 사전 정의 후보**로 제한했습니다. ① 결측 보정 + 성적 log1p + 표준화 + 연봉 로그 변환 Ridge(alpha=10), ② 같은 전처리 + 작은 ExtraTrees(64 trees, depth5). 선택 기준은 **학습80건 내부 5-fold CV MAE**뿐입니다. 각각 123,951,453원, 147,002,254원으로 Ridge를 선택했습니다. 전처리도 각 CV 학습 fold에만 fit됩니다. 선택 후 전체 학습80건으로 최종 fit한 다음 처음으로 테스트20건을 열었습니다. 이후 튜닝은 하지 않았습니다.

| 동일 최종 테스트20건 | 기존 미학습 계산식 | 선택된 Ridge |
|---|---:|---:|
| MAE (원) | 174,555,941 | 130,602,499 |
| RMSE (원) | 358,592,487 | 284,998,669 |
| R² | -0.2903 | 0.1850 |

MAE 25.18% 개선입니다. 기존 계산식은 단위가 다른 모든 성적을 합쳐 사실상 3천만~4천만원만 반환하여 고액 연봉을 심하게 과소 추정했습니다. 개선 모델도 최종 테스트의 켈리(실제14억원)에 약2.92억원을 제안하는 등 고액 계약 오차가 큽니다. 사전학습 범용 모델을 임의로 대체하지 않았으며, 현재 입력과 소규모 표본에 맞는 작은 회귀 모델을 사용했습니다. 20건 결과만으로 최신 KBO 전체에 대한 정확도를 보장할 수 없습니다. 세부 모델 카드: `ml/model-card.json`.

## Windows 로컬 실행

Python3.12, 설치된 Python을 사용하며 가상환경은 필수가 아닙니다.

```powershell
python -m pip install -r requirements.txt
python -m ml.build_model
# 터미널 1
python -m uvicorn api.main:app --host 127.0.0.1 --port 8001
# 터미널 2
python manage.py runserver 127.0.0.1:8000
```

직접 Python 실행의 웹은 `http://127.0.0.1:8000`, API 문서는 `http://127.0.0.1:8001/docs`입니다. Docker 자동 배포 주소는 아래처럼 기존 **8080**을 유지합니다. 이전 초기 모델 생성 명령 `ml.prepare_model`은 비교용 baseline만 생성하므로 현재 서비스 준비에는 사용하지 마세요.

100건 전체 재현과 최종 평가를 별도로 재현하려면:

```powershell
python -m ml.collect_data
python -m ml.experiment --evaluate
```

`ml/datasets/train.csv`(80건), `test.csv`(20건), 출처·분할 manifest가 생성됩니다. 테스트 CSV·모델 바이너리·선수별 오차 CSV·평가 이미지·관측 로그는 Git에서 제외합니다. 학습80건과 재현 가능한 출처/분할·평가 집계만 커밋합니다. Docker는 네트워크로 데이터를 다시 받지 않고 커밋된80건에서 **이미 선택된 후보만** 재현 fit합니다. 최종 테스트 파일은 이미지에 복사하지 않으며 빌드 중 존재 여부도 검사합니다. 재현 fit은 새 하이퍼파라미터 탐색이나 추가 개선 시도가 아닙니다.

## Docker / CI

```powershell
docker build -t kbo-salary:local .
docker run --rm -p 127.0.0.1:8000:8000 kbo-salary:local
```

Python3.12.12 베이스 digest, 직접/간접 의존성(`requirements-lock.txt`)은 고정되어 있습니다. Linux AMD64 Docker 이미지에서 모델 로드·추론·웹·정적 파일·API를 검증합니다. GitHub Secrets `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`은 `docker/login-action@v4`에서만 사용합니다. push마다 `계정/kbo-salary:sha-커밋SHA`, main에서 `latest`도 게시합니다. PR은 게시하지 않습니다. 모델 파일 대신 코드·학습80건을 이미지에 넣고 빌드 시 아티팩트를 생성합니다.

## Windows Runner 자동 배포와 관측

Runner는 `HOME`, 라벨 `[self-hosted, Windows, X64]`입니다. Docker Desktop은 Linux 컨테이너 모드로 켜 두고 Runner의 `run.cmd` 창도 유지하세요. `workflow_run`은 기본 브랜치에 있는 `deploy.yml`로 실행됩니다. main push의 CI가 성공했을 때만 그 CI의 정확한 SHA 이미지를 pull하며, 오래된 main 결과·PR·실패 CI는 배포하지 않습니다.

고정 프록시 `kbo-salary`가 기존 **http://127.0.0.1:8080**을 유지합니다. 후보 `kbo-salary-blue/green`을 독립적으로 검사하고 라우팅 파일을 atomic rename으로 전환합니다. 기존 요청은 요청 시작 시 선택된 backend에서 완료됩니다. 이전 backend는 다음 배포까지 살려 두며, 전환 후 검사 실패 시 기존 라우팅으로 복구합니다. 다른 컨테이너·이미지·방화벽·영구 보안정책은 변경하지 않습니다.

기존 직접 바인딩 컨테이너에서 이 고정 프록시로의 **최초 이관**에는 포트 소유권 이동이 필요합니다. 이 최초 이관은 무중단이라고 주장하지 않습니다. 실제 로컬 이관 관측40건 중39성공/1실패가 있었고, 별도 로그에 남겼습니다. 이후 같은 고정 프록시를 유지하는 배포의 무중단 여부는 각 실행의 실제 요청 로그 범위에서만 판정합니다.

CD는 서비스 변경 전에 **독립 Python 프로세스**로 고정된 holdout 행의 실제 `/api/v1/predict` POST 관측을 시작하고 첫 정상 응답을 확인해야 배포를 진행합니다. 요청이 끝난 뒤1초 쉬고 다음 요청을 보냅니다. UTC 시작/종료, 고해상도 응답시간, HTTP상태, 분석 유효성, 실제 응답 배포SHA·모델 버전을 UTF-8 JSONL에 기록합니다. 배포 성공/실패 모두 완료 후 최소30초를 추가 관측합니다. 이전 응답에 버전 필드가 없으면 `unknown-legacy`로 기록하며 추정해서 채우지 않습니다.

Actions 로그와 Step Summary에 전체 결과·대표 응답·버전 전환·성공/실패 수·실제 간격·최대 기록 공백을 출력합니다. 로그 완료 간격1.5초 초과 구간은 **UNVERIFIED**, 관측창 밖과 요청 사이도 연속 가용성이 보장된다고 표현하지 않습니다. `deployment-observation-실행ID-시도번호` Artifact에는 JSONL, stdout/stderr, 고정 요청, JSON/Markdown/HTML 요약과 가능한 경우 `summary.png`가 저장됩니다. 배포가 실패해도 `always()` 단계에서 수집합니다. `summary.html`은1440px 너비 한 화면 캡처용이며, 원본 세부값은 JSON에 남습니다. PNG 캡처는 설치된 Playwright/Edge를 이용하며 없어도 HTML·로그는 보존합니다.

독립 관측 포함 수동 재현:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/observe-deployment.ps1 -ImageRef f92m8c/kbo-salary:latest -DeploymentVersion manual
```

PowerShell 실행 옵션은 자식 프로세스에만 적용됩니다. Runner의 바깥 임시 `.ps1`에도 적용하도록 워크플로 `defaults.run.shell`을 설정했습니다. 지속 실행 서비스에는 `unless-stopped`를 사용합니다.

진단:

```powershell
docker ps --filter name=kbo-salary
docker logs --tail 60 kbo-salary
Invoke-RestMethod http://127.0.0.1:8080/health
```

8080 충돌은 소유 프로세스를 확인하고 임의 종료하지 마세요. Docker 접속 오류는 Runner를 실행한 사용자에서 Docker Desktop이 켜져 있는지 확인하세요. Runner 설치/인증/작업/로그, `.env`, 모델 바이너리, 캐시, 관측 로그와 스크린샷은 커밋하지 않습니다. 사용자 토큰이나 비밀번호를 로그에 출력하지 않습니다.
