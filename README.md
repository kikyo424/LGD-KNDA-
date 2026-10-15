# OLED Watch Trend Radar

야외 시인성을 위한 초고휘도 스마트워치·웨어러블 OLED 기술 동향을 무료 공개 API와 RSS로 수집하고 보여주는 정적 대시보드입니다. 국내 뉴스와 해외 논문을 전체·국내·해외로 나누어 탐색할 수 있습니다.

## 로컬 실행

```bash
npm install
python -m pip install -e .
python scripts/collect.py
npm run dev
```

## 원하는 키워드와 기간으로 수집

대시보드의 **맞춤 키워드 수집**에서 키워드, 시작일, 종료일, 자료 유형을 선택합니다. 로컬 실행도 필요하다면 아래 명령을 사용할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe scripts\collect.py --keyword "wearable OLED 3000 nits" --date-from 2024-01-01 --date-to 2026-12-31 --source all
```

배포 사이트에서는 **GitHub Actions에서 수집 시작**을 누른 뒤 열린 Actions 화면에서 같은 조건을 입력해 실행합니다. 완료 후 사이트를 새로고침하면 `최근 맞춤 수집 결과`에서 마지막 키워드, 기간, 자료 유형, 결과 건수와 해당 문서 필터를 확인할 수 있습니다.

`--source`는 `all`, `news`, `papers` 중 하나입니다. 맞춤 수집은 기존 데이터를 보존하면서 새 결과를 합치고 URL/DOI 기준으로 중복을 제거합니다. 사이트의 **가장 많이 나온 키워드** 영역에는 저장된 전체 결과의 키워드 빈도 상위 15개가 표시되며, 키워드를 누르면 관련 문서만 필터링됩니다.

네트워크 요청 없이 기존 데이터의 유사어 통합, 키워드 가중치, 중복 제거 및 품질 통계를 다시 계산할 수도 있습니다.

```powershell
.\.venv\Scripts\python.exe scripts\collect.py --reprocess-only
```

키워드는 `nit/nits → 휘도`, `high brightness/초고휘도 → 고휘도`, `tandem OLED/탠덤 → 탠덤 OLED`처럼 대표어로 통합됩니다. 제목은 2점, 요약은 1점으로 집계하며, 같은 날짜의 동일·재배포 뉴스 제목은 하나로 정리합니다. 제외·중복·누락·오류 통계는 `src/data/collection_quality.json`에 저장되어 대시보드에 표시됩니다.

## 최근 맞춤 수집 내역 지우기

대시보드의 **이 브라우저에서 숨기기**는 현재 브라우저에서만 최근 맞춤 수집 결과 카드를 숨깁니다. 다음 맞춤 수집이 완료되면 새 결과는 다시 표시됩니다.

모든 방문자에게 보이는 최근 맞춤 수집 내역을 지우려면 `Actions > Collect and deploy > Run workflow`에서 `clear_last_manual`을 선택해 실행하세요. 수집된 문서 데이터와 통계는 삭제하지 않고, 최근 맞춤 수집 요약만 초기화합니다.

로컬에서는 아래 명령으로 같은 작업을 할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe scripts\collect.py --clear-last-manual
```

## 최근 맞춤 수집 결과 삭제

`최근 맞춤 수집 결과`의 **이 결과 N건 삭제**를 누르고 확인하면 삭제 확인값과 Actions 링크가 표시됩니다. **Run workflow**에서 `delete_last_manual`에 확인값을 그대로 입력하고 실행하세요. 삭제 작업은 새 자료를 수집하지 않으며, 배포가 끝나면 해당 문서가 목록·검색·통계에서 제거되고 최근 수집 내역도 초기화됩니다.

삭제 대상은 **결과 N건 보기**와 동일한 문서입니다. 다른 수집과 겹치는 문서도 삭제되며, 이후 수집에서 다시 추가될 수 있습니다. 최근 수집이 바뀐 경우 오래된 확인값은 거부되므로 사이트를 새로고침하세요. `clear_last_manual`은 문서를 유지하고 요약만 초기화하는 기존 기능입니다.

로컬에서는 `python scripts/collect.py --delete-last-manual '<완료 시각>'`으로 같은 작업을 실행할 수 있습니다.

## 검증

```bash
python -m pytest
npm run build
```

## GitHub Pages

1. GitHub에 공개 저장소를 만듭니다.
2. 이 폴더를 `main` 브랜치에 push합니다.
3. 저장소 `Settings > Pages > Source`를 **GitHub Actions**로 설정합니다.
4. `Actions > Collect and deploy > Run workflow`로 첫 배포를 실행합니다.
5. 맞춤 수집 시 Run workflow 화면에서 `keyword`, `date_from`, `date_to`, `source`를 입력합니다. 수집 결과는 자동으로 `src/data/items.json`에 커밋되고 사이트가 다시 배포됩니다.

수집은 매일 한국 시간 오전 9시 17분에 자동 실행됩니다. 기본 OLED·웨어러블·COE 키워드로 뉴스와 논문 메타데이터를 수집하고 중복을 정리한 뒤 사이트를 자동 배포합니다. GitHub Actions 상황에 따라 실행 시간이 지연될 수 있습니다. Crossref의 polite pool을 사용하려면 저장소 Secret에 `CONTACT_EMAIL`을 추가하세요.

무료 학술 API를 안정적으로 사용하려면 `Settings > Secrets and variables > Actions`에 다음 Repository secrets를 선택적으로 추가하세요.

```text
CONTACT_EMAIL
SEMANTIC_SCHOLAR_API_KEY
OPENALEX_API_KEY
```

키가 없어도 수집은 계속되지만 Semantic Scholar의 무인증 공용 할당량은 혼잡 시 `429`를 반환할 수 있습니다. 한 수집원이 실패해도 다른 수집 결과와 사이트 배포는 유지됩니다.

## 데이터 원칙

- Crossref·arXiv의 해외 연구 메타데이터와 Google 뉴스 한국 RSS의 국내 기사 메타데이터를 저장합니다.
- 원문 전체를 복제하지 않고 제목, 초록, 날짜, DOI/URL, 기술 태그만 저장합니다.
- DOI 또는 고유 URL로 중복을 제거합니다.

## 기술 분류와 데이터 구조

수집 문서는 `초고휘도`, `저전력`, `발광 구조`, `야외 시인성`, `제조/공정`의 다중 분류를 가질 수 있습니다. 각 레코드는 다음 분석 필드를 포함합니다.

```text
document_id, source_type, title, published_date, company,
technology, keywords, summary, source_url, region, metrics
```

`metrics`에는 원문에 단위가 명시된 휘도, 반사율, 소비전력, 수명, 수율과 해당 문맥을 함께 저장합니다. 서로 다른 측정 조건의 값을 자동 순위화하지 않습니다.

현재 수집원은 Crossref, arXiv, Semantic Scholar, OpenAlex, Google 뉴스 한국 RSS입니다. Semantic Scholar와 OpenAlex는 무료 키를 환경변수로 선택적으로 사용할 수 있습니다. KIPRIS Plus는 무료 키 발급 후 특허 수집기로 확장합니다. Google Patents는 공식 공개 API가 없으므로 화면 자동 크롤링 대상에서 제외합니다.

