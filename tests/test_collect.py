import json

import scripts.collect as collect
from scripts.collect import deduplicate, extract_companies, extract_keyword_scores, extract_keywords, extract_metrics, in_date_range, is_relevant, news_title_fingerprint, normalize_date, paper_title_fingerprint, parse_args, parse_arxiv, parse_crossref, parse_openalex, parse_rss, parse_semantic_scholar, tag_technologies


def test_clear_last_manual_collection_preserves_a_valid_empty_summary(monkeypatch, tmp_path):
    target = tmp_path / "last_manual_collection.json"
    monkeypatch.setattr(collect, "LAST_MANUAL_FILE", target)

    collect.clear_last_manual_collection()

    assert json.loads(target.read_text(encoding="utf-8")) == {
        "keyword": "",
        "date_from": "",
        "date_to": "",
        "source": "all",
        "result_count": 0,
        "source_errors": 0,
        "completed_at": "",
    }


def test_tag_technologies_is_explainable():
    assert tag_technologies("Tandem OLED with LTPO for high brightness") == [
        "초고휘도",
        "저전력",
        "발광 구조",
    ]


def test_parse_crossref_normalizes_a_record():
    payload = {
        "message": {
            "items": [{
                "DOI": "10.1000/OLED",
                "title": ["High brightness <b>OLED</b> for wearables"],
                "abstract": "<jats:p>Improved sunlight readability.</jats:p>",
                "URL": "https://doi.org/10.1000/OLED",
                "issued": {"date-parts": [[2026, 4, 3]]},
            }]
        }
    }

    item = parse_crossref(payload)[0]

    assert item["published_at"] == "2026-04-03"
    assert item["title"] == "High brightness OLED for wearables"
    assert item["technologies"] == ["초고휘도", "야외 시인성"]


def test_parse_arxiv_and_deduplicate():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>https://arxiv.org/abs/2601.00001</id>
        <published>2026-01-02T00:00:00Z</published>
        <title>Polarizer-free top-emission OLED</title>
        <summary>Lower reflection and power consumption.</summary>
      </entry>
    </feed>"""

    item = parse_arxiv(xml)[0]
    assert item["technologies"] == ["저전력", "발광 구조", "야외 시인성"]
    assert len(deduplicate([item, item])) == 1


def test_normalize_date_accepts_partial_crossref_dates():
    assert normalize_date([[2026, None, None]]) == "2026-01-01"
    assert normalize_date([[None]]) == ""


def test_relevance_filter_excludes_non_display_wearables():
    assert is_relevant("High brightness OLED smartwatch display")
    assert not is_relevant("Wearable OLED patch for wound healing")


def test_parse_domestic_news_rss_assigns_region():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel><item>
      <title>삼성디스플레이, 스마트워치용 고휘도 OLED 공개</title>
      <link>https://example.com/oled-watch</link>
      <pubDate>Wed, 14 Oct 2026 09:00:00 GMT</pubDate>
      <description>야외 시인성을 개선한 LTPO OLED 기술</description>
      <source>테스트뉴스</source>
    </item></channel></rss>"""

    item = parse_rss(xml)[0]
    assert item["region"] == "domestic"
    assert item["source_type"] == "news"
    assert item["published_at"] == "2026-10-14"
    assert item["technologies"] == ["초고휘도", "저전력", "야외 시인성"]


def test_extracts_company_and_performance_metrics():
    text = "LG Display developed a 6,000 nits tandem OLED with reflectance 4.5% and lifetime 10,000 hours."
    assert extract_companies(text) == ["LG디스플레이"]
    metrics = extract_metrics(text)
    assert [(metric["name"], metric["value"]) for metric in metrics] == [
        ("brightness", 6000.0),
        ("reflectance", 4.5),
        ("lifetime", 10000.0),
    ]


def test_parse_semantic_scholar_record():
    item = parse_semantic_scholar({"data": [{
        "paperId": "paper-1", "title": "High brightness wearable OLED", "abstract": "6000 nits tandem OLED",
        "url": "https://example.com/paper", "publicationDate": "2025-05-01",
        "externalIds": {"DOI": "10.1000/test"}, "citationCount": 12,
    }]})[0]
    assert item["source"] == "Semantic Scholar"
    assert item["doi"] == "10.1000/test"
    assert item["citation_count"] == 12


def test_parse_openalex_reconstructs_abstract():
    item = parse_openalex({"results": [{
        "id": "https://openalex.org/W1", "display_name": "LTPO OLED power efficiency",
        "doi": "https://doi.org/10.1000/openalex", "publication_date": "2024-04-02",
        "abstract_inverted_index": {"Low": [0], "power": [1], "display": [2]}, "cited_by_count": 4,
    }]})[0]
    assert item["summary"] == "Low power display"
    assert item["doi"] == "10.1000/openalex"


def test_collection_excludes_pre_2023_documents_including_custom_results():
    dates = ["2022-12-31", "2023-01-01", "2026-01-01", "2022", ""]
    items = [{"id": str(index), "title": "OLED wearable display", "published_at": date, "custom_keyword": "OLED"} for index, date in enumerate(dates)]
    stats = {}
    result = deduplicate(items, stats)
    assert {item["published_at"] for item in result} == {"2023-01-01", "2026-01-01", ""}
    assert stats["excluded_before_2023"] == 2


def test_manual_collection_arguments_and_date_filter():
    args = parse_args(["--keyword", "blue OLED", "--date-from", "2025-01-01", "--date-to", "2025-12-31", "--source", "papers"])
    assert args.keyword == "blue OLED"
    assert args.source == "papers"
    assert in_date_range({"published_at": "2025-06-10"}, args.date_from, args.date_to)
    assert not in_date_range({"published_at": "2024-12-31"}, args.date_from, args.date_to)


def test_keyword_synonyms_are_combined_and_title_is_weighted():
    assert extract_keywords("High brightness display at 3000 nits") == ["고휘도", "휘도"]
    assert extract_keyword_scores("LTPO OLED", "LTPO improves power consumption") == {"LTPO": 3, "전력 효율": 1}


def test_syndicated_news_titles_share_a_fingerprint_and_are_removed():
    first = {"id": "one", "source_type": "news", "title": "[단독] 고휘도 OLED 공개 - 뉴스A", "summary": "스마트워치 OLED 휘도 향상", "published_at": "2026-01-01", "url": "https://a.example/1"}
    second = {**first, "id": "two", "title": "고휘도 OLED 공개 - 뉴스B", "url": "https://b.example/2"}
    stats = {}
    assert news_title_fingerprint(first["title"]) == news_title_fingerprint(second["title"])
    assert len(deduplicate([first, second], stats)) == 1
    assert stats["duplicates_removed"] == 1


def test_coe_display_variants_are_collected_as_one_keyword_and_paper_duplicates_merge():
    assert extract_keywords("COE display uses color filter on encapsulation") == ["COE display"]
    assert tag_technologies("COE OLED wearable display") == ["야외 시인성"]
    assert paper_title_fingerprint("COE-Display for Wearable OLED") == paper_title_fingerprint("coe display for wearable oled")
    first = {"id": "paper-a", "source_type": "paper", "title": "COE-Display for Wearable OLED", "summary": "Low reflection OLED wearable display", "published_at": "2025-01-01", "url": "https://a.example"}
    second = {**first, "id": "paper-b", "title": "COE display for wearable OLED", "url": "https://b.example"}
    assert len(deduplicate([first, second])) == 1



def test_delete_recent_results_removes_matching_documents_and_updates_reports(monkeypatch, tmp_path):
    monkeypatch.setattr(collect, "DATA_FILE", tmp_path / "items.json")
    monkeypatch.setattr(collect, "QUALITY_FILE", tmp_path / "quality.json")
    monkeypatch.setattr(collect, "LAST_MANUAL_FILE", tmp_path / "last.json")
    documents = [
        {"id": "delete", "custom_keyword": "OLED", "published_at": "2023-01-01"},
        {"id": "also-delete", "custom_keyword": "oled", "published_at": "2026-01-01"},
        {"id": "older-hidden", "custom_keyword": "OLED", "published_at": "2022-01-01"},
        {"id": "other", "custom_keyword": "LTPO", "published_at": "2026-01-01"},
        {"id": "default", "published_at": "2026-01-01"},
    ]
    collect.save(documents)
    collect.LAST_MANUAL_FILE.write_text(json.dumps({"keyword": "OLED", "completed_at": "timestamp"}))
    collect.QUALITY_FILE.write_text(json.dumps({"saved": 5, "duplicates_removed": 3, "source_errors": 1}))
    assert collect.main(["--delete-last-manual", "outdated"]) == 1
    assert collect.load_existing() == documents
    assert collect.main(["--delete-last-manual", "timestamp"]) == 0
    assert {item["id"] for item in collect.load_existing()} == {"older-hidden", "other", "default"}
    quality = json.loads(collect.QUALITY_FILE.read_text())
    assert quality["saved"] == 3
    assert quality["deleted_custom_results"] == 2
    assert quality["duplicates_removed"] == 3
    assert quality["source_errors"] == 1
    assert json.loads(collect.LAST_MANUAL_FILE.read_text())["keyword"] == ""
    assert collect.main(["--delete-last-manual", "timestamp"]) == 1


def test_international_google_news_uses_english_feed_and_preserves_publisher():
    xml = '''<rss><channel><item>
      <title>Smartwatch tandem OLED reaches 3000 nits</title>
      <link>https://example.com/watch</link>
      <pubDate>Wed, 14 Oct 2026 09:00:00 GMT</pubDate>
      <description>LTPO OLED improves power efficiency outdoors.</description>
      <source>Example Tech</source>
    </item></channel></rss>'''
    def respond(request):
        assert request.url.host == "news.google.com"
        assert request.url.params["hl"] == "en-US"
        assert request.url.params["gl"] == "US"
        assert request.url.params["ceid"] == "US:en"
        assert request.url.params["q"] == "smartwatch OLED"
        return collect.httpx.Response(200, text=xml)
    with collect.httpx.Client(transport=collect.httpx.MockTransport(respond)) as client:
        item = collect.fetch_international_news(client, "smartwatch OLED")[0]
    assert item["region"] == "international"
    assert item["source_type"] == "news"
    assert item["source"] == "Example Tech"
    assert item["published_at"] == "2026-10-14"
    assert "발광 구조" in item["technologies"]
    assert len(deduplicate([item, item])) == 1
    assert parse_rss(xml, fallback_source="Google News EN", region="international")[0]["id"] != parse_rss(xml)[0]["id"]


def test_manual_news_collection_saves_foreign_news_when_domestic_feed_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(collect, "DATA_FILE", tmp_path / "items.json")
    monkeypatch.setattr(collect, "QUALITY_FILE", tmp_path / "quality.json")
    monkeypatch.setattr(collect, "LAST_MANUAL_FILE", tmp_path / "last.json")
    def fail_domestic(client, query):
        raise collect.httpx.ConnectError("Unavailable")
    calls = []
    def foreign(client, query):
        calls.append(query)
        return [{"id": "foreign", "title": "Smartwatch OLED high brightness", "published_at": "2026-10-14", "source_type": "news", "region": "international", "source": "Example Tech", "url": "https://example.com/watch"}]
    monkeypatch.setattr(collect, "fetch_domestic_news", fail_domestic)
    monkeypatch.setattr(collect, "fetch_international_news", foreign)
    assert collect.main(["--keyword", "smartwatch OLED", "--source", "news", "--date-from", "2026-01-01"]) == 0
    assert calls == ["smartwatch OLED"]
    item = collect.load_existing()[0]
    assert item["region"] == "international"
    assert item["custom_keyword"] == "smartwatch OLED"
    assert json.loads(collect.QUALITY_FILE.read_text())["source_errors"] == 1
    assert json.loads(collect.LAST_MANUAL_FILE.read_text())["result_count"] == 1


def test_html_report_collects_all_routes_without_changing_dashboard(monkeypatch, tmp_path):
    for name, filename in [("DATA_FILE", "items.json"), ("QUALITY_FILE", "quality.json"), ("LAST_MANUAL_FILE", "last.json")]:
        path = tmp_path / filename
        path.write_text('[{"id":"existing-dashboard-only"}]')
        monkeypatch.setattr(collect, name, path)
    before = {name: getattr(collect, name).read_bytes() for name in ("DATA_FILE", "QUALITY_FILE", "LAST_MANUAL_FILE")}
    calls = []
    def fetch(name, kind):
        def run(client, query, *args):
            calls.append(name)
            assert query == "smartwatch OLED"
            return [{"id": name, "title": f"{name} smartwatch OLED high brightness", "published_at": "2026-01-01", "source_type": kind, "source": name, "region": "international", "url": f"https://example.com/{name}", "summary": "LTPO OLED"}]
        return run
    for name in ("crossref", "arxiv", "semantic_scholar", "openalex", "domestic_news", "international_news"):
        monkeypatch.setattr(collect, "fetch_" + name, fetch(name, "news" if name.endswith("news") else "paper"))
    monkeypatch.setattr(collect.time, "sleep", lambda seconds: None)
    output = tmp_path / "report.html"
    assert collect.main(["--keyword", "smartwatch OLED", "--source", "all", "--report-output", str(output)]) == 0
    assert len(calls) == 6
    report = output.read_text()
    assert "existing-dashboard-only" not in report
    assert "전체<b>6건" in report
    assert "뉴스<b>2건" in report
    assert "논문<b>4건" in report
    assert 'src="http' not in report and 'href="http' in report
    assert all(getattr(collect, name).read_bytes() == original for name, original in before.items())


def test_html_report_all_failed_still_writes_diagnostic_file(monkeypatch, tmp_path):
    def fail(client, query):
        raise collect.httpx.ConnectError("Service unavailable")
    monkeypatch.setattr(collect, "fetch_domestic_news", fail)
    monkeypatch.setattr(collect, "fetch_international_news", fail)
    monkeypatch.setattr(collect, "load_existing", lambda: (_ for _ in ()).throw(AssertionError("must not read dashboard")))
    output = tmp_path / "failed.html"
    assert collect.main(["--keyword", "OLED", "--source", "news", "--report-output", str(output)]) == 1
    report = output.read_text()
    assert "수집 경로 오류 2건" in report
    assert "검색 조건에 해당하는 자료가 없습니다" in report


def test_html_report_escapes_remote_content_and_rejects_unsafe_links(tmp_path):
    from scripts.html_report import write_report
    args = parse_args(["--keyword", '<script>alert("test")</script>', "--report-output", str(tmp_path / "safe.html")])
    write_report(args.report_output, args, [{"title": '<img src=x onerror="alert(1)">', "url": "javascript:alert(1)", "summary": "<script>bad()</script>", "source_type": "news", "region": "international", "source": "Test", "keywords": ["LTPO"]}], ["<script>failure</script>"])
    report = args.report_output.read_text()
    assert "<script>" not in report
    assert "<img" not in report
    assert "javascript:" not in report
    assert "&lt;script&gt;" in report
