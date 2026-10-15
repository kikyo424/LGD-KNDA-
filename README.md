# OLED Watch Trend Radar

야외 시인성을 위한 초고휘도 스마트워치·웨어러블 OLED 기술 동향을 무료 공개 API와 RSS로 수집하고 보여주는 정적 대시보드입니다. 국내·해외 뉴스와 해외 논문을 전체·국내·해외로 나누어 탐색할 수 있습니다.

## 로컬 실행

```bash
npm install
python -m pip install -e .
python scripts/collect.py
npm run dev
```

## 맞춤 키워드 HTML 보고서

대시보드의 **맞춤 키워드 HTML 보고서**에서 키워드·기간·자료 유형을 입력하고 **HTML 보고서 만들기**를 누르세요. 표시된 조건을 **Custom HTML report → Run workflow**에 입력해 실행합니다. 해외 자료는 영문 키워드를 권장합니다.

완료된 실행 화면 하단 **Artifacts**에서 `custom-html-report-실행번호` ZIP을 다운로드하고 압축을 푼 뒤 `custom-report.html`을 브라우저에서 여세요. 보고서는 30일간 보관됩니다. GitHub 로그인과 워크플로 실행 권한이 필요합니다.

보고서에는 검색 조건, 생성 시각(한국 시간), 뉴스·논문 건수, 키워드별 자료 수, 출처 현황, 최신순 문서 목록·제공된 요약·원문 링크 및 수집 경로 오류가 포함됩니다. 스타일과 데이터가 파일 안에 포함되므로 인터넷 없이 읽을 수 있습니다. 원문 링크를 열 때만 인터넷이 필요합니다.

국내·영문 해외 Google 뉴스 RSS와 Crossref·arXiv·Semantic Scholar·OpenAlex를 기존과 동일하게 사용합니다. 2023년 이전 자료를 제외하고 중복을 정리하며, 이번 검색에서 수집한 자료만 보고서에 포함합니다. 기존 사이트 데이터는 합치거나 변경하지 않고, 보고서 생성 시 사이트를 재배포하지 않습니다. 결과가 없으면 빈 결과 보고서, 일부 경로가 실패하면 오류 안내가 포함된 보고서를 제공합니다. 전 경로 실패로 결과가 없는 경우 워크플로가 실패하더라도 생성된 HTML은 Artifacts에서 확인할 수 있습니다.

로컬에서도 실행할 수 있습니다.

```bash
python scripts/collect.py --keyword "wearable OLED 3000 nits" --date-from 2024-01-01 --date-to 2026-12-31 --source all --report-output reports/custom-report.html
```

`--source`는 `all`, `news`, `papers` 중 하나입니다. `reports/`는 Git에서 제외됩니다.

매일 자동 수집과 사이트 배포는 **Collect and deploy**가 담당합니다. 기존 데이터의 분류·중복·품질 통계만 다시 계산하려면 `python scripts/collect.py --reprocess-only`를 사용할 수 있습니다. 사이트 상위 키워드는 해당 키워드가 포함된 자료 수 기준입니다.

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
5. 맞춤 수집은 별도의 **Custom HTML report** 워크플로에서 실행하고 HTML 파일로 다운로드합니다.

수집은 매일 한국 시간 오전 9시 17분에 자동 실행됩니다. 기본 OLED·웨어러블·COE 키워드로 뉴스와 논문 메타데이터를 수집하고 중복을 정리한 뒤 사이트를 자동 배포합니다. GitHub Actions 상황에 따라 실행 시간이 지연될 수 있습니다. Crossref의 polite pool을 사용하려면 저장소 Secret에 `CONTACT_EMAIL`을 추가하세요.

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

수집 문서는 `초고휘도`, `저전력`, `발광 구조`, `야외 시인성`, `제조/공정`의 다중 분류를 가질 수 있습니다. 각 레코드는 다음 분석 필드를 포함합니다.

```text
document_id, source_type, title, published_date, company,
technology, keywords, summary, source_url, region, metrics
```

`metrics`에는 원문에 단위가 명시된 휘도, 반사율, 소비전력, 수명, 수율과 해당 문맥을 함께 저장합니다. 서로 다른 측정 조건의 값을 자동 순위화하지 않습니다.

현재 수집원은 Crossref, arXiv, Semantic Scholar, OpenAlex, Google 뉴스 한국·미국 영문 RSS입니다. 해외 뉴스는 영문 검색어로 조회하며 `해외` 필터에 포함됩니다. 맞춤 수집에서 `뉴스`를 선택하면 국내·해외 RSS를 함께 조회합니다. Semantic Scholar와 OpenAlex는 무료 키를 환경변수로 선택적으로 사용할 수 있습니다. KIPRIS Plus는 무료 키 발급 후 특허 수집기로 확장합니다. Google Patents는 공식 공개 API가 없으므로 화면 자동 크롤링 대상에서 제외합니다.

