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
