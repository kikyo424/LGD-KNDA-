from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "src" / "data" / "items.json"
QUALITY_FILE = ROOT / "src" / "data" / "collection_quality.json"
LAST_MANUAL_FILE = ROOT / "src" / "data" / "last_manual_collection.json"
USER_AGENT = "oled-watch-trend-radar/0.1 (academic trend research)"

QUERIES = [
    'OLED (smartwatch OR wearable) (brightness OR "sunlight readability")',
    'OLED (tandem OR LTPO OR "polarizer free") wearable',
    'OLED ("COE display" OR "COE OLED" OR "color filter on encapsulation") wearable',
]

SCHOLAR_QUERIES = [
    'wearable OLED high brightness sunlight readability',
    'LTPO OLED power efficiency tandem low reflection',
    'wearable OLED COE display color filter on encapsulation',
]

DOMESTIC_NEWS_QUERIES = [
    'OLED (스마트워치 OR 웨어러블) (고휘도 OR 야외시인성 OR 휘도)',
    'OLED (LTPO OR 탠덤 OR 무편광판 OR 반사율) (LG디스플레이 OR 삼성디스플레이)',
    'OLED (COE OR 컬러필터온인캡슐레이션 OR 무편광판) (스마트워치 OR 웨어러블 OR 디스플레이)',
]

INTERNATIONAL_NEWS_QUERIES = [
    'OLED (smartwatch OR wearable) (brightness OR sunlight OR luminance)',
    'OLED (LTPO OR tandem OR "polarizer free" OR reflectance) (watch OR wearable)',
    'OLED ("COE display" OR "COE OLED" OR "color filter on encapsulation")',
]

TECHNOLOGIES = {
    "초고휘도": ("high brightness", "ultra-high luminance", "peak brightness", "peak luminance", "nit", "nits", "초고휘도", "고휘도", "최대 휘도"),
    "저전력": ("ltpo", "low-temperature polycrystalline oxide", "power efficiency", "power consumption", "energy efficiency", "low power", "소비전력", "전력 효율", "저전력"),
    "발광 구조": ("tandem oled", "tandem structure", "oled emitter", "emissive layer", "top-emission", "top emission", "tandem woled", "탠덤", "발광 소재", "발광층"),
    "야외 시인성": ("sunlight readable", "sunlight readability", "low reflection", "low reflectance", "polarizer-free", "polarizer free", "color filter on encapsulation", "coe oled", "coe display", "co-e display", "micro lens array", "microlens array", "ambient contrast", "야외 시인성", "저반사", "반사율", "무편광판"),
    "제조/공정": ("oled yield", "manufacturing cost", "mass production", "production yield", "fabrication process", "encapsulation", "양산", "수율", "제조 비용", "공정", "원가"),
}

# 같은 개념의 표기를 하나로 합쳐 키워드 순위가 철자 차이로 분산되지 않게 한다.
KEYWORD_CANONICAL = {
    "high brightness": "고휘도", "ultra-high luminance": "고휘도", "peak brightness": "고휘도", "peak luminance": "고휘도",
    "nit": "휘도", "nits": "휘도", "초고휘도": "고휘도", "최대 휘도": "고휘도",
    "low-temperature polycrystalline oxide": "LTPO", "ltpo": "LTPO",
    "power efficiency": "전력 효율", "power consumption": "전력 효율", "energy efficiency": "전력 효율", "low power": "전력 효율", "소비전력": "전력 효율", "저전력": "전력 효율",
    "tandem oled": "탠덤 OLED", "tandem structure": "탠덤 OLED", "tandem woled": "탠덤 OLED", "탠덤": "탠덤 OLED",
    "oled emitter": "발광 소재", "emissive layer": "발광 소재", "발광층": "발광 소재",
    "top-emission": "Top-emission", "top emission": "Top-emission",
    "sunlight readable": "야외 시인성", "sunlight readability": "야외 시인성", "ambient contrast": "야외 시인성",
    "low reflection": "저반사", "low reflectance": "저반사", "반사율": "저반사",
    "polarizer-free": "무편광판", "polarizer free": "무편광판",
    "coe oled": "COE display", "coe display": "COE display", "co-e display": "COE display", "color filter on encapsulation": "COE display",
    "micro lens array": "MLA", "microlens array": "MLA",
    "oled yield": "수율", "production yield": "수율", "manufacturing cost": "제조 원가", "제조 비용": "제조 원가", "원가": "제조 원가",
    "mass production": "양산", "fabrication process": "제조 공정", "공정": "제조 공정", "encapsulation": "봉지 공정",
}

COMPANIES = {
    "LG디스플레이": ("lg display", "lg디스플레이", "lgd"),
    "삼성디스플레이": ("samsung display", "삼성디스플레이", "삼성d", "sdc"),
    "BOE": ("boe", "京东方"),
    "Apple": ("apple", "애플"),
    "Universal Display": ("universal display", "udc"),
    "Japan Display": ("japan display", "jdi"),
    "TCL CSOT": ("tcl csot", "csot"),
}

OLED_TERMS = ("oled", "올레드", "organic light emitting", "organic light-emitting")
DISPLAY_SIGNALS = (
    "smartwatch", "smart watch", "wearable display", "watch display",
    "brightness", "luminance", "sunlight", "outdoor visibility", "reflectance",
    "tandem", "ltpo", "polarizer", "top-emission", "top emission",
    "micro lens", "microlens", "coe display", "coe oled", "color filter on encapsulation", "amoled", "스마트워치", "야외 시인성",
    "휘도", "반사율", "탠덤", "무편광판",
)


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", html.unescape(value))
    return re.sub(r"\s+", " ", without_tags).strip()


def tag_technologies(*values: str) -> list[str]:
    content = " ".join(values).lower()
    tags = [name for name, terms in TECHNOLOGIES.items() if any(term in content for term in terms)]
    # COE의 정식 명칭 안의 encapsulation은 봉지 공정 자체를 뜻하지 않는다.
    if "color filter on encapsulation" in content and "제조/공정" in tags:
        other_process_terms = tuple(term for term in TECHNOLOGIES["제조/공정"] if term != "encapsulation")
        if not any(term in content for term in other_process_terms):
            tags.remove("제조/공정")
    return tags


def extract_keywords(*values: str) -> list[str]:
    content = " ".join(values).lower()
    matched_terms = {term for terms in TECHNOLOGIES.values() for term in terms if term in content}
    if "color filter on encapsulation" in content:
        matched_terms.discard("encapsulation")
    return sorted({KEYWORD_CANONICAL.get(term, term) for term in matched_terms}, key=str.lower)


def extract_keyword_scores(title: str, summary: str) -> dict[str, int]:
    """제목 출현은 2점, 요약 출현은 1점으로 계산한다."""
    title_keywords = set(extract_keywords(title))
    summary_keywords = set(extract_keywords(summary))
    return {keyword: (2 if keyword in title_keywords else 0) + (1 if keyword in summary_keywords else 0)
            for keyword in sorted(title_keywords | summary_keywords, key=str.lower)}


def news_title_fingerprint(title: str) -> str:
    normalized = re.sub(r"^\[[^]]+\]\s*", "", clean_text(title).lower())
    normalized = re.sub(r"\s+[-|]\s+[^-|]+$", "", normalized)
    return re.sub(r"[^0-9a-z가-힣]+", "", normalized)


def paper_title_fingerprint(title: str) -> str:
    """출처가 다른 같은 논문의 표기 차이(공백·하이픈·대소문자)를 통합한다."""
    return re.sub(r"[^0-9a-z가-힣]+", "", clean_text(title).lower())


def extract_companies(*values: str) -> list[str]:
    content = " ".join(values).lower()
    return [name for name, aliases in COMPANIES.items() if any(alias in content for alias in aliases)]


def extract_metrics(*values: str) -> list[dict[str, Any]]:
    number = r"(?<![\da-zA-Z.,−–—-])(?P<value>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
    patterns = (
        ("brightness", number + r"\s*(?P<unit>nits?|cd\s*/?\s*m(?:²|2))(?![a-zA-Z])"),
        ("reflectance", r"(?:reflectance|reflection|반사율)[^\d.;%]{0,45}" + number + r"\s*(?P<unit>%)"),
        ("power", r"(?:power consumption|consum(?:es|ed|ing)|소비전력)[^\d.;%]{0,45}" + number + r"\s*(?P<unit>m?w)(?![a-zA-Z])"),
        ("lifetime", r"(?:lifetime|수명|LT(?:50|90|95|97))[^\d.;%]{0,45}" + number + r"\s*(?P<unit>hours?|hrs?|시간|h)(?![a-zA-Z])"),
    )
    metrics = []
    seen = set()
    for value in values:
        # Keep titles and summaries separate, and retain the full evidence sentence.
        sentences = re.split(r"(?<=[.!?。！？])\s+(?=[A-Za-z가-힣])|[;\n]+", clean_text(value))
        for sentence in sentences:
            for name, pattern in patterns:
                for match in re.finditer(pattern, sentence, flags=re.IGNORECASE):
                    numeric = float(match.group("value").replace(",", ""))
                    if numeric <= 0 or (name == "reflectance" and numeric > 100):
                        continue
                    if name == "brightness" and not re.search(r"brightness|luminance|휘도|밝기|oled|올레드", sentence, re.I):
                        continue
                    if name == "brightness" and (
                        re.search(r"(?:by|of)\s*$", sentence[max(0, match.start() - 25):match.start()], re.I)
                        and re.search(r"increas|decreas|improv|reduc", sentence, re.I)
                        or re.match(r"\s*(?:만큼|증가|감소|향상)", sentence[match.end():])
                    ):
                        continue
                    if name == "reflectance" and re.search(r"reduc|decreas|improv|증가|감소|개선|절감|낮[아췄추]", sentence, re.I):
                        continue
                    if name == "power":
                        if not re.search(r"oled|올레드|panel|display|패널|디스플레이|소자", sentence, re.I):
                            continue
                        if re.search(r"battery|배터리|(?:device|system|smartwatch|watch)\s+(?:total\s+)?power|(?:total|overall)\s+(?:device|system|watch)|(?:기기|시스템|스마트워치)(?:의)?\s*(?:전체|총)?\s*소비전력", sentence, re.I):
                            continue
                    if name == "lifetime":
                        if not re.search(r"oled|올레드|emitter|발광|소자", sentence, re.I):
                            continue
                        if re.search(r"battery|배터리|test(?:ing)? (?:time|duration)|시험\s*시간|테스트\s*시간", sentence, re.I):
                            continue
                        if re.search(r"improv|increas|extend|향상|증가|연장", match.group(), re.I):
                            continue
                    unit = match.group("unit")
                    if name == "brightness":
                        unit = "nits" if unit.lower().startswith("nit") else "cd/m²"
                    elif name == "power":
                        unit = "mW" if unit.lower().startswith("m") else "W"
                    elif name == "lifetime":
                        unit = "시간"
                    target = "측정 대상 미공개"
                    if re.search(r"smart\s*watch|스마트워치|스마트 워치", sentence, re.I):
                        target = "스마트워치 관련"
                    elif re.search(r"\bTV\b|television|smartphone|phone|vehicle|laptop|notebook|tablet|monitor|microdisplay|텔레비전|스마트폰|차량|노트북|태블릿|모니터", sentence, re.I):
                        target = "타 기기 관련"
                    elif re.search(r"wearable|웨어러블", sentence, re.I):
                        target = "웨어러블 관련 (스마트워치 여부 미공개)"
                    elif re.search(r"panel|display|패널|디스플레이", sentence, re.I):
                        target = "패널·디스플레이"
                    elif re.search(r"device|emitter|소자|발광체", sentence, re.I):
                        target = "소자·발광체"
                    elif re.search(r"oled|올레드", sentence, re.I):
                        target = "OLED (세부 대상 미공개)"
                    qualifier = ""
                    if name == "brightness":
                        if re.search(r"peak|maximum|max\b|최대|피크", sentence, re.I):
                            qualifier = "최대 휘도 언급"
                        elif re.search(r"sustained|continuous|지속|연속", sentence, re.I):
                            qualifier = "지속 휘도 언급"
                        prefix = sentence[max(0, match.start() - 20):match.start()]
                        if re.search(r"\bfrom\s*$", prefix, re.I):
                            qualifier = "비교 기준값"
                        elif re.search(r"\bto\s*$", prefix, re.I):
                            qualifier = "변경 후 보고값"
                        elif re.search(r"\b(?:at|under)\s*$", prefix, re.I):
                            qualifier = "측정·구동 조건값"
                    if name == "lifetime":
                        lifetime_type = re.search(r"\bLT(?:50|90|95|97)\b", sentence, re.I)
                        if lifetime_type:
                            qualifier = lifetime_type.group().upper()
                    conditions = [entry.group().strip() for entry in re.finditer(
                        r"(?:APL|OPR|주사율|refresh rate|initial luminance|초기 휘도)\s*(?:of|at|[:=])?\s*\d+(?:\.\d+)?\s*(?:%|Hz|nits?|cd/m²)|\d+(?:\.\d+)?\s*(?:°C|℃|Hz)", sentence, re.I)]
                    evidence_key = re.sub(r"[\W_]+", "", sentence).casefold()
                    key = (name, numeric, unit, evidence_key)
                    if key in seen:
                        continue
                    seen.add(key)
                    metrics.append({"name": name, "value": numeric, "unit": unit,
                                    "context": sentence.strip(), "target": target,
                                    "qualifier": qualifier, "conditions": conditions})
    return metrics


def is_relevant(*values: str) -> bool:
    content = " ".join(values).lower()
    return any(term in content for term in OLED_TERMS) and any(term in content for term in DISPLAY_SIGNALS)


def stable_id(source: str, identifier: str) -> str:
    return hashlib.sha256(f"{source}:{identifier}".encode("utf-8")).hexdigest()[:20]


def normalize_date(parts: list[list[int]] | None) -> str:
    if not parts or not parts[0]:
        return ""
    values = parts[0]
    year, month, day = (values + [1, 1])[:3]
    if year is None:
        return ""
    month = month or 1
    day = day or 1
    try:
        return datetime(year, month, day, tzinfo=UTC).date().isoformat()
    except ValueError:
        return ""


def parse_crossref(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for record in payload.get("message", {}).get("items", []):
        title = clean_text(" ".join(record.get("title", [])))
        if not title:
            continue
        doi = record.get("DOI", "").lower()
        url = record.get("URL") or (f"https://doi.org/{doi}" if doi else "")
        identifier = doi or url or title
        summary = clean_text(record.get("abstract"))
        results.append({
            "id": stable_id("crossref", identifier),
            "doi": doi,
            "source_type": "paper",
            "source": "Crossref",
            "region": "international",
            "title": title,
            "published_at": normalize_date((record.get("published-print") or record.get("published-online") or record.get("issued") or {}).get("date-parts")),
            "url": url,
            "summary": summary[:700],
            "technologies": tag_technologies(title, summary),
            "collected_at": datetime.now(UTC).isoformat(),
        })
    return results


def parse_arxiv(xml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    results = []
    for entry in root.findall("atom:entry", namespace):
        title = clean_text(entry.findtext("atom:title", default="", namespaces=namespace))
        summary = clean_text(entry.findtext("atom:summary", default="", namespaces=namespace))
        url = entry.findtext("atom:id", default="", namespaces=namespace)
        published = entry.findtext("atom:published", default="", namespaces=namespace)
        if not title or not url:
            continue
        results.append({
            "id": stable_id("arxiv", url),
            "doi": "",
            "source_type": "paper",
            "source": "arXiv",
            "region": "international",
            "title": title,
            "published_at": published[:10],
            "url": url,
            "summary": summary[:700],
            "technologies": tag_technologies(title, summary),
            "collected_at": datetime.now(UTC).isoformat(),
        })
    return results


def parse_rss(xml_text: str, fallback_source: str = "Google 뉴스 KR", region: str = "domestic") -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    results = []
    for entry in root.findall("./channel/item"):
        title = clean_text(entry.findtext("title", default=""))
        summary = clean_text(entry.findtext("description", default=""))
        url = clean_text(entry.findtext("link", default=""))
        source = clean_text(entry.findtext("source", default="")) or fallback_source
        published_raw = clean_text(entry.findtext("pubDate", default=""))
        if not title or not url:
            continue
        try:
            published_at = parsedate_to_datetime(published_raw).date().isoformat()
        except (TypeError, ValueError):
            published_at = ""
        results.append({
            "id": stable_id(f"{region}-news", url),
            "doi": "",
            "source_type": "news",
            "source": source,
            "region": region,
            "title": title,
            "published_at": published_at,
            "url": url,
            "summary": summary[:700],
            "technologies": tag_technologies(title, summary),
            "collected_at": datetime.now(UTC).isoformat(),
        })
    return results


def parse_semantic_scholar(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for record in payload.get("data", []):
        title = clean_text(record.get("title"))
        summary = clean_text(record.get("abstract"))
        paper_id = record.get("paperId", "")
        url = record.get("url") or (f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else "")
        if not title or not paper_id:
            continue
        external_ids = record.get("externalIds") or {}
        results.append({
            "id": stable_id("semantic-scholar", paper_id),
            "doi": clean_text(external_ids.get("DOI")).lower(),
            "source_type": "paper",
            "source": "Semantic Scholar",
            "region": "international",
            "title": title,
            "published_at": clean_text(record.get("publicationDate"))[:10] or str(record.get("year") or ""),
            "url": url,
            "summary": summary[:700],
            "technologies": tag_technologies(title, summary),
            "citation_count": record.get("citationCount") or 0,
            "collected_at": datetime.now(UTC).isoformat(),
        })
    return results


def openalex_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    if not inverted_index:
        return ""
    words = [(position, word) for word, positions in inverted_index.items() for position in positions]
    return " ".join(word for _, word in sorted(words))


def parse_openalex(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for record in payload.get("results", []):
        title = clean_text(record.get("display_name") or record.get("title"))
        summary = clean_text(openalex_abstract(record.get("abstract_inverted_index")))
        work_id = clean_text(record.get("id"))
        if not title or not work_id:
            continue
        doi_url = clean_text(record.get("doi"))
        doi = doi_url.removeprefix("https://doi.org/").lower()
        results.append({
            "id": stable_id("openalex", work_id),
            "doi": doi,
            "source_type": "paper",
            "source": "OpenAlex",
            "region": "international",
            "title": title,
            "published_at": clean_text(record.get("publication_date"))[:10],
            "url": doi_url or work_id,
            "summary": summary[:700],
            "technologies": tag_technologies(title, summary),
            "citation_count": record.get("cited_by_count") or 0,
            "collected_at": datetime.now(UTC).isoformat(),
        })
    return results


def deduplicate(items: list[dict[str, Any]], stats: dict[str, int] | None = None) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    excluded = duplicates = excluded_before_2023 = 0
    for item in items:
        year = clean_text(item.get("published_at"))[:4]
        if year.isdigit() and len(year) == 4 and int(year) < 2023:
            excluded_before_2023 += 1
            continue
        if not item.get("custom_keyword") and not is_relevant(item.get("title", ""), item.get("summary", "")):
            excluded += 1
            continue
        item["region"] = item.get("region") or ("domestic" if item.get("source_type") == "news" else "international")
        title, summary = item.get("title", ""), item.get("summary", "")
        item["document_id"] = item["id"]
        item["published_date"] = item.get("published_at", "")
        item["company"] = extract_companies(title, summary)
        item["technology"] = tag_technologies(title, summary)
        item["technologies"] = item["technology"]
        item["keywords"] = extract_keywords(title, summary)
        item["keyword_scores"] = extract_keyword_scores(title, summary)
        # custom_keyword는 수집 이력으로만 보존한다. 원문에 없는 검색어를
        # 빈도에 넣으면 상위 키워드가 인위적으로 부풀려지므로 집계하지 않는다.
        item["metrics"] = extract_metrics(title, summary)
        item["source_url"] = item.get("url", "")
        if item.get("doi"):
            key = f"doi:{item['doi'].lower()}"
        elif item.get("source_type") == "news":
            key = f"news:{item.get('published_at', '')}:{news_title_fingerprint(title)}"
        elif item.get("source_type") == "paper":
            key = f"paper:{item.get('published_at', '')[:4]}:{paper_title_fingerprint(title)}"
        else:
            key = item["id"]
        previous = unique.get(key)
        if previous:
            duplicates += 1
        if previous and len(previous.get("summary", "")) > len(item.get("summary", "")):
            continue
        unique[key] = item
    result = sorted(unique.values(), key=lambda item: (item.get("published_at", ""), item["id"]), reverse=True)
    if stats is not None:
        stats.update({"input": len(items), "excluded_irrelevant": excluded, "excluded_before_2023": excluded_before_2023, "duplicates_removed": duplicates, "saved": len(result)})
    return result


def fetch_crossref(client: httpx.Client, query: str, email: str | None) -> list[dict[str, Any]]:
    params = {"query": query, "rows": 30, "select": "DOI,title,abstract,URL,published-print,published-online,issued"}
    if email:
        params["mailto"] = email
    response = client.get("https://api.crossref.org/works", params=params)
    response.raise_for_status()
    return parse_crossref(response.json())


def fetch_arxiv(client: httpx.Client, query: str) -> list[dict[str, Any]]:
    encoded_query = quote_plus(f'all:"{query}"')
    url = f"https://export.arxiv.org/api/query?search_query={encoded_query}&start=0&max_results=30&sortBy=submittedDate&sortOrder=descending"
    response = client.get(url)
    response.raise_for_status()
    return parse_arxiv(response.text)


def fetch_domestic_news(client: httpx.Client, query: str) -> list[dict[str, Any]]:
    encoded_query = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    response = client.get(url)
    response.raise_for_status()
    return parse_rss(response.content.decode("utf-8"))


def fetch_international_news(client: httpx.Client, query: str) -> list[dict[str, Any]]:
    response = client.get(
        "https://news.google.com/rss/search",
        params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
    )
    response.raise_for_status()
    return parse_rss(response.content.decode("utf-8"), fallback_source="Google News EN", region="international")


def fetch_semantic_scholar(client: httpx.Client, query: str, api_key: str | None) -> list[dict[str, Any]]:
    headers = {"x-api-key": api_key} if api_key else None
    response = None
    for attempt in range(3):
        response = client.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={
                "query": query,
                "limit": 30,
                "fields": "paperId,title,abstract,url,year,publicationDate,externalIds,citationCount",
            },
            headers=headers,
        )
        if response.status_code != 429:
            break
        retry_after = float(response.headers.get("retry-after", 2 ** (attempt + 1)))
        time.sleep(min(retry_after, 10))
    assert response is not None
    response.raise_for_status()
    return parse_semantic_scholar(response.json())


def fetch_openalex(client: httpx.Client, query: str, email: str | None, api_key: str | None) -> list[dict[str, Any]]:
    params = {"search": query, "per-page": 25}
    if email:
        params["mailto"] = email
    if api_key:
        params["api_key"] = api_key
    response = client.get("https://api.openalex.org/works", params=params)
    response.raise_for_status()
    return parse_openalex(response.json())


def load_existing() -> list[dict[str, Any]]:
    if not DATA_FILE.exists():
        return []
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save(items: list[dict[str, Any]]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = DATA_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(DATA_FILE)


def document_identity(item: dict[str, Any]) -> set[str]:
    identities = {f"{field}:{str(item[field]).strip().lower()}" for field in ("id", "url", "doi") if item.get(field)}
    title = clean_text(item.get("title"))
    if title:
        if item.get("source_type") == "news":
            identities.add(f"news:{item.get('published_at', '')}:{news_title_fingerprint(title)}")
        else:
            identities.add(f"paper:{item.get('published_at', '')[:4]}:{paper_title_fingerprint(title)}")
    return identities


def build_collection_update(existing: list[dict[str, Any]], items: list[dict[str, Any]], errors: list[str]) -> dict[str, Any]:
    known = set().union(*(document_identity(item) for item in existing))
    added = [item for item in items if document_identity(item).isdisjoint(known)]
    return {
        "completed_at": datetime.now(UTC).isoformat(),
        "new_count": len(added),
        "new_documents": added,
        "source_errors": len(errors),
    }


def save_quality(stats: dict[str, Any], items: list[dict[str, Any]], errors: list[str]) -> None:
    previous = json.loads(QUALITY_FILE.read_text(encoding="utf-8")) if QUALITY_FILE.exists() else {}
    report = {
        **({"last_update": previous["last_update"]} if "last_update" in previous else {}),
        **stats,
        "missing_date": sum(not item.get("published_at") for item in items),
        "missing_summary": sum(not item.get("summary") for item in items),
        "source_errors": len(errors),
        "generated_at": datetime.now(UTC).isoformat(),
    }
    QUALITY_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_last_manual_collection(args: argparse.Namespace, items: list[dict[str, Any]], errors: list[str]) -> None:
    """정적 사이트에서도 마지막 맞춤 수집 결과를 표시할 수 있도록 요약을 저장한다."""
    keyword = clean_text(args.keyword)
    if not keyword:
        return
    matching = [item for item in items if clean_text(item.get("custom_keyword")).lower() == keyword.lower()]
    report = {
        "keyword": keyword,
        "date_from": args.date_from or "",
        "date_to": args.date_to or "",
        "source": args.source,
        "result_count": len(matching),
        "source_errors": len(errors),
        "completed_at": datetime.now(UTC).isoformat(),
    }
    LAST_MANUAL_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clear_last_manual_collection() -> None:
    """Keep collected documents while clearing only the displayed custom-collection summary."""
    report = {
        "keyword": "",
        "date_from": "",
        "date_to": "",
        "source": "all",
        "result_count": 0,
        "source_errors": 0,
        "completed_at": "",
    }
    LAST_MANUAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_MANUAL_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def delete_last_manual_results(expected_completed_at: str) -> int:
    report = json.loads(LAST_MANUAL_FILE.read_text(encoding="utf-8"))
    keyword = report.get("keyword", "").lower()
    if not keyword or report.get("completed_at") != expected_completed_at:
        raise ValueError("최근 수집 내역이 변경되었습니다. 사이트를 새로고침한 뒤 삭제를 다시 요청하세요.")
    existing = load_existing()
    def matches(item: dict[str, Any]) -> bool:
        published = item.get("published_at", "")
        year = published[:4]
        visible = not re.match(r"\d{4}", published) or int(year) >= 2023
        return visible and item.get("custom_keyword", "").lower() == keyword
    remaining = [item for item in existing if not matches(item)]
    removed = len(existing) - len(remaining)
    save(remaining)
    stats = json.loads(QUALITY_FILE.read_text(encoding="utf-8")) if QUALITY_FILE.exists() else {}
    stats.update({"saved": len(remaining), "deleted_custom_results": removed})
    errors = stats.get("source_errors", 0)
    save_quality(stats, remaining, [""] * errors)
    clear_last_manual_collection()
    return removed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect OLED trend metadata")
    parser.add_argument("--keyword", help="Custom keyword or search phrase")
    parser.add_argument("--date-from", help="Inclusive start date in YYYY-MM-DD")
    parser.add_argument("--date-to", help="Inclusive end date in YYYY-MM-DD")
    parser.add_argument("--source", choices=("all", "news", "papers"), default="all")
    parser.add_argument("--reprocess-only", action="store_true", help="Rebuild tags, quality scores and duplicates without network requests")
    parser.add_argument("--report-output", type=Path, help="Write a standalone HTML report without changing dashboard data (requires --keyword)")
    parser.add_argument("--clear-last-manual", action="store_true", help="Clear the recent custom collection summary without deleting documents")
    parser.add_argument("--delete-last-manual", metavar="COMPLETED_AT", help="Delete the displayed recent custom results using their completion timestamp")
    args = parser.parse_args(argv)
    if args.report_output and (not clean_text(args.keyword) or args.reprocess_only or args.clear_last_manual or args.delete_last_manual):
        parser.error("--report-output requires --keyword and cannot be combined with reprocess or deletion options")
    if args.report_output and (args.report_output.suffix.lower() != ".html" or args.report_output.resolve().is_relative_to((ROOT / "src").resolve())):
        parser.error("--report-output must be an .html file outside src/")
    for field in ("date_from", "date_to"):
        value = getattr(args, field)
        if value:
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError as exc:
                parser.error(f"--{field.replace('_', '-')} must be YYYY-MM-DD: {exc}")
    if args.date_from and args.date_to and args.date_from > args.date_to:
        parser.error("--date-from must not be later than --date-to")
    return args


def in_date_range(item: dict[str, Any], date_from: str | None, date_to: str | None) -> bool:
    published = clean_text(item.get("published_at"))[:10]
    if (date_from or date_to) and len(published) != 10:
        return False
    return not ((date_from and published < date_from) or (date_to and published > date_to))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.delete_last_manual:
        try:
            removed = delete_last_manual_results(args.delete_last_manual)
        except (ValueError, FileNotFoundError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"Deleted {removed} recent custom collection documents")
        return 0
    if args.clear_last_manual:
        clear_last_manual_collection()
        print(f"Cleared recent custom collection summary in {LAST_MANUAL_FILE}")
        return 0
    custom_keyword = clean_text(args.keyword)
    is_manual = bool(custom_keyword)
    # 정기 수집의 RSS 결과는 최신 제목을 반영하고, 맞춤 수집은 기존 결과에 추가한다.
    existing = [] if args.report_output else load_existing()
    previous_items = list(existing)
    collected = existing if is_manual or args.reprocess_only else [item for item in existing if item.get("region") != "domestic"]
    paper_queries = [custom_keyword] if is_manual else QUERIES
    scholar_queries = [custom_keyword] if is_manual else SCHOLAR_QUERIES
    news_queries = [custom_keyword] if is_manual else DOMESTIC_NEWS_QUERIES
    international_news_queries = [custom_keyword] if is_manual else INTERNATIONAL_NEWS_QUERIES
    email = os.getenv("CONTACT_EMAIL")
    semantic_scholar_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    openalex_key = os.getenv("OPENALEX_API_KEY")
    headers = {"User-Agent": f"{USER_AGENT}{f' mailto:{email}' if email else ''}"}
    errors = []

    def add_results(results: list[dict[str, Any]]) -> None:
        for item in results:
            if not in_date_range(item, args.date_from, args.date_to):
                continue
            if is_manual:
                item["custom_keyword"] = custom_keyword
            collected.append(item)

    with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as client:
        if args.reprocess_only:
            paper_queries = scholar_queries = news_queries = international_news_queries = []
        for index, query in enumerate(paper_queries if args.source != "news" else []):
            try:
                if index:
                    time.sleep(1.1)
                add_results(fetch_crossref(client, query, email))
            except (httpx.HTTPError, ValueError) as exc:
                errors.append(f"Crossref/{query}: {exc}")
            try:
                if index:
                    time.sleep(3)
                add_results(fetch_arxiv(client, query))
            except (httpx.HTTPError, ET.ParseError) as exc:
                errors.append(f"arXiv/{query}: {exc}")
        for query in news_queries if args.source != "papers" else []:
            try:
                add_results(fetch_domestic_news(client, query))
            except (httpx.HTTPError, ET.ParseError) as exc:
                errors.append(f"Domestic news/{query}: {exc}")
        for query in international_news_queries if args.source != "papers" else []:
            try:
                add_results(fetch_international_news(client, query))
            except (httpx.HTTPError, ET.ParseError) as exc:
                errors.append(f"International news/{query}: {exc}")
        for query in scholar_queries if args.source != "news" else []:
            try:
                add_results(fetch_semantic_scholar(client, query, semantic_scholar_key))
            except (httpx.HTTPError, ValueError) as exc:
                errors.append(f"Semantic Scholar/{query}: {exc}")
            time.sleep(1.1)
            try:
                add_results(fetch_openalex(client, query, email, openalex_key))
            except (httpx.HTTPError, ValueError) as exc:
                errors.append(f"OpenAlex/{query}: {exc}")
            time.sleep(1.1)

    quality_stats: dict[str, Any] = {}
    final_items = deduplicate(collected, quality_stats)
    if args.report_output:
        if __package__:
            from .html_report import write_report
        else:
            from html_report import write_report
        for name in ("CONTACT_EMAIL", "SEMANTIC_SCHOLAR_API_KEY", "OPENALEX_API_KEY"):
            value = os.getenv(name)
            if value:
                errors = [error.replace(value, "[redacted]") for error in errors]
        write_report(args.report_output, args, final_items, errors)
        print(f"Saved standalone HTML report with {len(final_items)} documents to {args.report_output}")
        return 0 if final_items or not errors else 1
    save(final_items)
    if not args.reprocess_only:
        quality_stats["last_update"] = build_collection_update(previous_items, final_items, errors)
    save_quality(quality_stats, final_items, errors)
    save_last_manual_collection(args, final_items, errors)
    print(f"Saved {len(final_items)} unique documents to {DATA_FILE}")
    for error in errors:
        print(f"WARNING: {error}", file=sys.stderr)
    return 0 if final_items or not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

