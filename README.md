# KBO 다음 시즌 연봉 제안 웹 서비스

## Docker / GitHub Actions

이 저장소의 루트는 `upload` 폴더입니다. `Dockerfile`, `.dockerignore`, `requirements-lock.txt`, `.github/workflows/ci.yml`과 함께 변경된 소스를 저장소에 반영하세요.

### 빌드와 실행 (PowerShell)

```powershell
docker build -t kbo-salary:local .
docker run --rm -p 127.0.0.1:8000:8000 --name kbo-salary kbo-salary:local
```

웹은 `http://127.0.0.1:8000`, API 문서는 같은 주소의 `/docs`입니다. 컨테이너는 FastAPI와 Django를 하나의 ASGI 서비스로 실행하고 웹에서 상대 경로로 API를 호출합니다. 로컬의 별도 API 서버(8001)는 필요하지 않습니다. 종료는 실행 창에서 `Ctrl+C`를 누릅니다.

외부 도메인에서 실행할 때는 `-e DJANGO_ALLOWED_HOSTS=example.com -e DJANGO_SECRET_KEY=<실제-비밀값>`을 실행 환경에서 전달하세요. 인증 정보는 이미지나 저장소에 저장하지 않습니다.

### 자동 빌드 및 Docker Hub 게시

GitHub 저장소의 **Settings → Secrets and variables → Actions → Repository secrets**에 다음 두 Secrets를 등록해야 합니다.

- `DOCKERHUB_USERNAME`: Docker Hub 계정명
- `DOCKERHUB_TOKEN`: 해당 계정의 `kbo-salary` 저장소에 쓰기 가능한 액세스 토큰

Docker Hub에 계정 소유의 `kbo-salary` 저장소를 준비하세요. 워크플로는 push마다 Linux AMD64 이미지를 빌드하고, 다음 검증이 모두 통과한 **동일 이미지**를 `<DOCKERHUB_USERNAME>/kbo-salary:sha-<전체 커밋 SHA>`로 게시합니다. 기본 브랜치 push에서는 `latest` 태그도 갱신합니다. Pull Request에서는 빌드·검증만 수행하며 Secrets와 이미지 게시를 사용하지 않습니다. Actions 화면에서 수동 실행도 가능합니다.

1. 고정된 의존성 설치 및 `pip check`
2. Linux 이미지 내부에서 초기 모델 생성 → 역직렬화 → 타자/투수 양수 정수 예측 검사
3. Django 설정 검사와 정적 파일 수집
4. 최종 비관리자 이미지에서 모델 로드 재검사
5. 컨테이너 실행 후 웹·JavaScript·CSS·예측 API의 HTTP 통합 검사
6. 검증 컨테이너 종료·제거 후 Docker Hub 로그인 및 게시

```powershell
docker pull <DOCKERHUB_USERNAME>/kbo-salary:latest
docker run --rm -p 127.0.0.1:8000:8000 <DOCKERHUB_USERNAME>/kbo-salary:latest
```

### 고정 버전과 모델 처리

Python `3.12.12-slim-bookworm` 베이스 이미지와 SHA256 digest를 고정했습니다. 직접 의존성은 `requirements.txt`, Linux의 간접 의존성까지 포함한 잠금 목록은 `requirements-lock.txt`에 있습니다. 주요 ML 버전은 scikit-learn 1.9.1, NumPy 2.5.2, SciPy 1.18.1, pandas 3.1.0, joblib 1.6.0입니다. Django는 기존 6.1.2에서 수정 릴리스 6.1.3으로 반영했습니다. 잠금 파일은 Linux 컨테이너용이며 Windows에서는 기존처럼 `requirements.txt`를 사용합니다.

현재 모델은 데이터가 없는 초기 모델입니다. 빌드할 때 코드에서 새로 생성하므로 GitHub에 모델을 업로드할 필요가 없습니다. `.dockerignore`는 기존 모델·학습 데이터·캐시·로그·비밀 파일·Git/Codex 설정을 빌드 컨텍스트에서 제외합니다. 생성된 작은 초기 모델만 이미지 내부에 포함됩니다.

향후 학습된 모델은 신뢰할 수 있는 별도 저장소에서 제공받고, 읽기 전용 볼륨으로 마운트해 `SALARY_MODEL_PATH` 환경변수로 지정할 수 있습니다. joblib은 신뢰하는 출처의 파일만 로드하세요. 학습 환경과 추론 환경의 scikit-learn/NumPy/joblib 버전을 동일하게 맞춰야 하며, 초기 모델을 생성하는 현재 빌드 절차를 실제 모델 검증 절차로 교체해야 합니다.

참고: [Docker 공식 GitHub Actions 가이드](https://docs.docker.com/build/ci/github-actions/push-multi-registries/), [Django 6.1.3 수정 내역](https://docs.djangoproject.com/en/6.1/releases/6.1.3/).

프로야구 선수의 해당 시즌 성적(타자 또는 투수)을 입력하면 다음 시즌의 제안 연봉(KRW)을 반환하는 Django 웹과 FastAPI 예측 API입니다.

> 현재 포함된 모델은 **학습 전 초기 모델**입니다. 개발 연동 확인을 위해 양수 정수값을 반환할 뿐, 실제 계약·연봉 판단에 사용하면 안 됩니다.

## 저장소에 포함하지 않은 항목

이 폴더에는 인증 정보, 개인 정보, `.env`, Codex 설정, 캐시·로그, 테스트 데이터, 학습 데이터, 그리고 생성·학습된 모델 파일을 넣지 않았습니다. 모델 아티팩트(`ml/artifacts/salary_model.joblib`)는 아래 과정으로 각 실행 환경에서 생성하거나 학습해야 합니다.

## 설치

Python 3.12 이상에서 실행합니다. 가상환경 사용 여부는 선택 사항입니다.

```bash
python -m pip install -r requirements.txt
cp .env.example .env  # Windows PowerShell: Copy-Item .env.example .env
```

`.env`의 값은 예시이므로 실제 배포 환경에서는 배포 서비스의 환경변수 설정에 입력합니다. `.env` 파일을 커밋하지 마세요.

## 모델 준비와 로컬 실행

초기 모델을 생성합니다.

```bash
python -m ml.prepare_model
```

터미널 두 개에서 각각 실행합니다.

```bash
# API
python -m uvicorn api.main:app --host 127.0.0.1 --port 8001

# 웹 (다른 터미널)
python manage.py runserver 127.0.0.1:8000
```

브라우저에서 `http://127.0.0.1:8000`을 열고, API 문서는 `http://127.0.0.1:8001/docs`에서 확인합니다.

로컬에서도 WhiteNoise가 CSS와 JavaScript 원본을 제공합니다. 수정 후에는 `Ctrl+F5`로 새로고침하세요. 타자/투수 선택에 따라 해당 유형의 입력란만 활성화되며, 선택 유형은 제목과 계산 결과에 표시됩니다. 계산 실패 시 API 서버도 실행 중인지 확인하세요.

## 실제 데이터 학습

CSV에는 다음 열과 목표 열 `next_salary_krw`가 필요합니다.

`games`, `plate_appearances`, `batting_average`, `home_runs`, `rbi`, `stolen_bases`, `games_pitched`, `innings_pitched`, `wins`, `saves`, `era`, `strikeouts`, `next_salary_krw`

```bash
python -m ml.train data/salaries.csv
```

이 명령은 `ml/artifacts/salary_model.joblib`을 생성합니다. 이 파일과 원본 데이터는 대용량·민감성 관리 정책에 따라 저장소 외부의 접근 제어된 저장소에 보관하세요. 학습 전에 누수 점검, 시계열 분리 평가, 오차·편향 분석 및 도메인 검토가 필요합니다.

## 배포 설정

웹과 API는 별도 서비스로 배포합니다. `render.yaml`은 Render Blueprint용 예시이며, GitHub 저장소 루트에 이 폴더의 **내용물**을 올린 뒤 사용할 수 있습니다.

1. API 서비스 환경변수: `CORS_ALLOWED_ORIGINS=https://<웹-도메인>`을 설정합니다.
2. 웹 서비스 환경변수: 강한 `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS=<웹-도메인>`, `SALARY_API_URL=https://<API-도메인>`을 설정합니다.
3. 데이터로 학습한 모델을 배포할 경우, 빌드 또는 안전한 모델 저장소에서 `ml/artifacts/salary_model.joblib`을 주입하는 절차를 별도로 구성합니다. 공개 GitHub 저장소에 모델 파일이나 데이터를 올리지 마세요.

`render.yaml`의 초기 모델 생성은 기능 확인용입니다. 실제 서비스에서는 검증된 학습 모델을 안전하게 공급하도록 해당 빌드 명령을 바꾸세요.
