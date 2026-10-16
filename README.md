# OLED Watch Trend Radar

야외 시인성을 위한 초고휘도 스마트워치·웨어러블 OLED 기술 동향을 무료 공개 API와 RSS로 수집하고 보여주는 정적 대시보드입니다. 국내·해외 뉴스와 해외 논문을 전체·국내·해외로 나누어 탐색할 수 있습니다.

## 로컬 실행

```bash
npm install
python -m pip install -e .
python scripts/collect.py
npm run dev
```

## 사이트에서 맞춤 HTML 보고서 받기

방문자는 **맞춤 키워드 HTML 보고서**에서 키워드·기간·자료 유형을 입력하고 **HTML 보고서 만들기**를 누릅니다. 진행 상태가 표시되고, 완료되면 같은 화면의 **HTML 보고서 다운로드**로 파일을 받습니다. 방문자의 GitHub 계정이나 Actions 조작은 필요하지 않습니다.

국내·영문 해외 Google 뉴스 RSS와 Crossref·arXiv·Semantic Scholar·OpenAlex를 사용합니다. 이번 검색 자료만 독립 HTML 파일로 만들며, 기존 대시보드 데이터는 바꾸지 않습니다. 검색 조건·출처·문서 목록·제공된 요약·키워드 통계·오류 내역을 포함합니다. 수집 경로 일부가 실패해도 결과 보고서에 오류가 표시되며, 전부 실패하면 오류 내역 보고서를 제공합니다.

### 무료 수집 서버 연결 (운영자 최초 1회)

GitHub Pages는 정적 사이트이므로 수집 실행용 서버가 별도로 필요합니다. `render.yaml`은 **Render 무료 Web Service** 1개만 선언합니다. 유료 인스턴스·데이터베이스·디스크는 사용하지 않습니다. 실제 이용 조건과 무료 한도는 배포 시 서비스에서 확인하세요.

1. Render 계정에서 이 저장소를 연결하고 **New → Blueprint**로 `render.yaml`을 배포합니다. Web Service 플랜이 **Free**인지 확인합니다. 직접 Web Service를 만들 경우 Python 런타임(Python 3.11 이상)을 선택하고 `render.yaml`의 buildCommand·startCommand를 사용합니다.
2. 생성된 서버 주소에서 `/health`가 `{"status":"ok"}`를 반환하는지 확인합니다.
3. 현재 사이트의 기본 수집 서버는 `https://oled-report-service.onrender.com`으로 연결되어 있습니다. 서버를 바꾸려면 GitHub 저장소 **Settings → Secrets and variables → Actions → Variables**에 `REPORT_API_URL`을 새 서버의 HTTPS 주소로 추가합니다. 경로는 넣지 않습니다. 이 값이 있으면 기본 주소보다 우선합니다.
4. **Collect and deploy**를 한 번 실행해 사이트를 다시 배포합니다. 이후 방문자는 사이트 안에서만 수집·다운로드를 이용합니다.
5. 실제 키워드로 보고서를 만들고 다운로드해 각 수집원 결과를 확인합니다. 코드 테스트만으로 외부 수집원 접근 가능 여부나 공개 배포 성공을 보장하지 않습니다.

서버의 `REPORT_ALLOWED_ORIGINS`는 현재 사이트 `https://kikyo424.github.io`로 설정됩니다. 도메인을 바꾸면 이 값도 수정하세요. 선택 API 키는 서버의 환경 설정에 보관하고 프런트엔드에 넣지 않습니다.

무료 서버는 유휴 시 절전 또는 재시작될 수 있어 첫 연결이 늦거나 진행 중 작업이 사라질 수 있습니다. 보고서는 최대 1시간 임시 보관하며 서버 재시작 시 소실됩니다. 완료 즉시 다운로드하세요. 동시 실행 2개, 대기 포함 4개, 보관 30개, IP당 10분에 3회로 제한합니다. 서버는 메모리 작업 상태를 사용하므로 **worker 1개·인스턴스 1개**로 실행합니다. 별도 유료 기능은 활성화하지 않습니다.

### 로컬 실행

```bash
python -m pip install -e '.[server,test]'
python -m uvicorn scripts.report_server:app --host 127.0.0.1 --port 8765 --workers 1
```

다른 터미널에서 `PUBLIC_REPORT_API_URL=http://127.0.0.1:8765 npm run dev`를 실행하면 사이트에서 수집을 요청할 수 있습니다.

서버 없이 로컬 파일로만 수집할 수도 있습니다.

```bash
python scripts/collect.py --keyword "wearable OLED 3000 nits" --date-from 2024-01-01 --date-to 2026-12-31 --source all --report-output reports/custom-report.html
```

관리자용 **Custom HTML report** Actions 워크플로도 보조 수단으로 남아 있습니다. 이 경로로 만든 파일은 실행 화면의 Artifacts에서 30일간 다운로드할 수 있습니다. 매일 자동 수집과 사이트 배포는 기존 **Collect and deploy**가 담당합니다.

## 검증

### 외부 예약으로 매일 자동 업데이트

사이트에는 관리자 입력칸이나 업데이트 실행 버튼이 없습니다. cron-job.org에서 매일 한국 시간 09:10에 Render API를 호출하면 GitHub Actions가 수집·배포를 수행합니다. 예약 서비스 계정에서 아래 작업을 최초 1회 등록해야 하며, 코드 배포만으로 외부 예약이 생성되지는 않습니다.

Render의 기존 `oled-report-service > Environment`에서 다음 두 비밀 환경변수를 설정하고 최신 코드를 배포하세요.

- `UPDATE_ADMIN_KEY`: 길고 무작위인 서버 간 인증키. 아래 예약 작업의 Authorization 헤더에만 등록합니다. 사이트에서 입력할 필요가 없습니다.
- `UPDATE_GITHUB_TOKEN`: GitHub Fine-grained personal access token. `kikyo424/LGD-KNDA-` 저장소만 선택하고 Repository permissions의 **Actions: Read and write**를 부여합니다. 토큰은 서버에만 저장합니다. 만료되면 Render에서 교체합니다.

`render.yaml`에 두 항목을 비밀 입력으로 선언했습니다. 이미 생성된 서비스는 Render 환경변수에서 직접 추가할 수 있습니다. 이 저장소에 Render가 연결되어 있으면 최신 코드 자동 배포 여부를 확인하고, 자동 배포가 꺼져 있으면 `Manual Deploy > Deploy latest commit`을 실행하세요. 환경변수가 없으면 API는 실행을 거부하고 설정 필요 메시지를 표시합니다. 설정 값을 코드나 채팅에 붙여넣지 마세요.

cron-job.org에서 아래 두 작업을 등록하세요. 시간대는 모두 `Asia/Seoul`이며 매일 반복합니다.

| 작업 | 시간 | 방식 | URL |
| --- | --- | --- | --- |
| 서버 깨우기 | 09:07 | GET | `https://oled-report-service.onrender.com/health` |
| 업데이트 실행 | 09:10 | POST | `https://oled-report-service.onrender.com/updates` |

업데이트 실행 작업의 고급 설정에서 헤더 `Authorization`을 `Bearer <Render의 UPDATE_ADMIN_KEY 값>`으로 설정합니다. 본문은 비워둡니다. GitHub 토큰은 Render에만 저장합니다. 서버 주소를 변경했다면 두 URL을 함께 수정합니다. 서버 깨우기는 무료 Render의 절전 후 첫 응답 지연을 줄이기 위한 보조 요청이며 정시 응답을 보장하지 않습니다.

테스트 실행에서 업데이트 요청이 HTTP 202와 요청 `id`를 반환하는지 확인한 뒤, GitHub Actions의 `Navigator MAP update <id>` 실행이 성공했는지 확인하세요. HTTP 202는 요청 접수이지 배포 완료가 아닙니다. 401은 인증키 불일치, 503은 Render 환경변수 누락, 409는 이미 실행 중이거나 최근 접수한 요청, 502는 GitHub 권한/설정 오류, 504는 GitHub 응답 지연입니다. 응답이 불명확하면 재실행 전에 Actions 기록을 확인합니다. 예약 서비스의 실패 알림과 실행 기록도 활성화하세요.

외부 예약 실행 성공을 확인할 때까지 기존 GitHub 09:10 `schedule`은 임시 예비 경로로 유지합니다. 외부 등록이 확인되면 `.github/workflows/pages.yml`의 `schedule` 블록을 제거하여 예약 경로를 통일합니다. 외부 계정 설정이 안 된 상태에서 예비 경로를 먼저 제거하지 마세요.

공식 설정 문서: https://docs.cron-job.org/creating-cron-jobs.html · https://render.com/docs/free

업데이트 API: `POST /updates`, `GET /updates/{요청UUID}`. 두 요청 모두 `Authorization: Bearer <UPDATE_ADMIN_KEY>` 인증이 필요합니다. 이미 실행 중인 워크플로가 있으면 중복 요청을 거부하고, 접수 후 2분간 추가 요청을 제한합니다. 10분간 인증 실패 5회인 IP는 일시 차단합니다. 제한은 단일 서버 메모리를 사용하며 재시작 시 초기화됩니다. 실행 상태는 요청 UUID가 붙은 GitHub 실행 기록에서 조회하므로 서버 재시작 후에도 다른 실행과 혼동하지 않습니다. 이 기능의 실제 운영 확인에는 Render 비밀 환경변수 설정이 필요합니다.

```bash
python -m pytest
npm run build
```

## GitHub Pages

1. GitHub에 공개 저장소를 만듭니다.
2. 이 폴더를 `main` 브랜치에 push합니다.
3. 저장소 `Settings > Pages > Source`를 **GitHub Actions**로 설정합니다.
4. `Actions > Collect and deploy > Run workflow`로 첫 배포를 실행합니다.
5. 맞춤 수집 서버를 위 절차대로 연결하면 방문자가 사이트에서 HTML 보고서를 직접 다운로드할 수 있습니다.

수집 목표 시각은 매일 한국 시간 오전 9시 10분입니다. 위 외부 예약 등록을 완료하면 Render를 통해 실행되며, 기존 GitHub 예약(`10 0 * * *`, UTC 00:10)은 외부 실행 확인 전까지 예비 경로로 유지합니다. 기본 OLED·웨어러블·COE 키워드로 뉴스와 논문 메타데이터를 수집하고 중복을 정리한 뒤 사이트를 자동 배포합니다. 시작 시각은 서비스 상황에 따라 지연될 수 있고, 사이트에는 수집과 배포가 완료된 뒤 반영됩니다. Crossref의 polite pool을 사용하려면 저장소 Secret에 `CONTACT_EMAIL`을 추가하세요.

최근 업데이트 신규 자료는 수집 직전 데이터와 비교해 집계하며, 기존 ID·URL·DOI 또는 동일 제목·발표일로 확인되는 자료는 신규에서 제외합니다. 새 자료가 없으면 0건을 표시합니다. 신규 내역 보기에서 제목을 눌러 원문을 열 수 있으며, 수집 오류가 발생한 경우 함께 안내합니다. 단순 데이터 재처리는 마지막 신규 집계를 유지합니다.

무료 학술 API를 안정적으로 사용하려면 `Settings > Secrets and variables > Actions`에 다음 Repository secrets를 선택적으로 추가하세요.

```text
CONTACT_EMAIL
SEMANTIC_SCHOLAR_API_KEY
OPENALEX_API_KEY
```

키가 없어도 수집은 계속되지만 Semantic Scholar의 무인증 공용 할당량은 혼잡 시 `429`를 반환할 수 있습니다. 한 수집원이 실패해도 다른 수집 결과와 사이트 배포는 유지됩니다.

## 데이터 원칙

- Crossref·arXiv의 해외 연구 메타데이터와 Google 뉴스 한국·미국 영문 RSS의 국내·해외 기사 메타데이터를 저장합니다.
- 원문 전체를 복제하지 않고 제목, 초록, 날짜, DOI/URL, 기술 태그만 저장합니다.
- DOI 또는 고유 URL로 중복을 제거합니다.

## 기술 분류와 데이터 구조

### 키워드별 4개 기준 근거 현황

상위 키워드를 선택하고 **4개 기준 근거 현황 보기**를 눌러야 결과가 나타납니다. 주제 관련 표현, 추출 성능 수치, 적용 대상 언급, 제조·개발 관련 표현을 기준으로 자료 수와 출처 문장을 정리합니다. AI 평가나 기술 추천 점수가 아니며, 실제 스마트워치 적용·제조 난이도·상용화 단계는 원문 검토가 필요합니다. 근거를 찾지 못한 경우 부정적 결론 대신 `원문 확인 필요`로 표시합니다. 대상 분류는 스마트워치 → 웨어러블 → 타 기기 → 실험 소자 → 확인 필요 순서로 자료당 한 번만 적용하며 다른 기준의 건수는 겹칠 수 있습니다. 자동 수집 후 사이트를 빌드할 때 함께 갱신됩니다.

집계 규칙 테스트는 `npm run test:evidence`로 실행합니다.

### 문헌에 보고된 성능 지표

제목과 제공된 요약에서 휘도(nits·cd/m²), 반사율(%), 패널·디스플레이 소비전력(W·mW), OLED 발광 수명(시간)을 규칙으로 추출합니다. 수율, 반사율 감소·개선율, 배터리 사용시간, 기기 전체 소비전력은 제외합니다. 의미가 불명확한 표현은 보수적으로 제외하므로 모든 수치를 추출하지는 않습니다.

각 항목에 근거 문장 전체, 문헌 내 대상(문맥 기준), 명시된 측정 조건, 출처를 표시합니다. 조건을 찾지 못하면 `원문 확인 필요`로 표시합니다. 같은 수치도 서로 다른 문헌이면 유지하고, 같은 문서의 같은 근거만 중복 제거합니다. 화면과 문서당 추출 개수 제한은 없습니다. PDF 본문·표는 분석하지 않으며 자동 판독 결과이므로 실제 비교 전 원문을 확인해야 합니다.

수집 문서는 `초고휘도`, `저전력`, `발광 구조`, `야외 시인성`, `제조/공정`의 다중 분류를 가질 수 있습니다. 각 레코드는 다음 분석 필드를 포함합니다.

```text
document_id, source_type, title, published_date, company,
technology, keywords, summary, source_url, region, metrics
```

`metrics`에는 원문에 단위가 명시된 휘도, 반사율, 소비전력, 수명, 수율과 해당 문맥을 함께 저장합니다. 서로 다른 측정 조건의 값을 자동 순위화하지 않습니다.

현재 수집원은 Crossref, arXiv, Semantic Scholar, OpenAlex, Google 뉴스 한국·미국 영문 RSS입니다. 해외 뉴스는 영문 검색어로 조회하며 `해외` 필터에 포함됩니다. 맞춤 수집에서 `뉴스`를 선택하면 국내·해외 RSS를 함께 조회합니다. Semantic Scholar와 OpenAlex는 무료 키를 환경변수로 선택적으로 사용할 수 있습니다. KIPRIS Plus는 무료 키 발급 후 특허 수집기로 확장합니다. Google Patents는 공식 공개 API가 없으므로 화면 자동 크롤링 대상에서 제외합니다.

