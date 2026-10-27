# KBO 다음 시즌 연봉 제안 웹 서비스

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
