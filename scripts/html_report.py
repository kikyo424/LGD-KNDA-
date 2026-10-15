"""Render a standalone report without changing the dashboard's stored data."""
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo


def write_report(path: Path, args, items: list[dict], errors: list[str]) -> None:
    def text(value):
        return escape(str(value or ""), quote=True)

    keywords = Counter(keyword for item in items for keyword in set(item.get("keywords", [])))
    sources = Counter(item.get("source", "출처 미상") for item in items)
    source_label = {"all": "뉴스 + 논문", "news": "뉴스", "papers": "논문"}[args.source]
    generated = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M")
    cards = []
    for item in items:
        url = item.get("url", "")
        safe_url = url if urlsplit(url).scheme.lower() in ("http", "https") else ""
        title = text(item.get("title"))
        link = f'<a href="{text(safe_url)}" target="_blank" rel="noopener noreferrer">{title}</a>' if safe_url else title
        kind = "뉴스" if item.get("source_type") == "news" else "논문"
        region = "국내" if item.get("region") == "domestic" else "해외"
        tags = "".join(f"<span>{text(keyword)}</span>" for keyword in item.get("keywords", []))
        cards.append(f'<article><div class="meta">{kind} · {region} · {text(item.get("source"))} · {text(item.get("published_at") or "날짜 미상")}</div><h3>{link}</h3><p>{text(item.get("summary") or "제공된 요약이 없습니다. 원문 링크를 확인하세요.")}</p><div class="tags">{tags}</div></article>')
    def counts(values):
        return "".join(f"<li><span>{text(name)}</span><b>{count}건</b></li>" for name, count in sorted(values.items(), key=lambda pair: (-pair[1], pair[0]))) or "<li>자료 없음</li>"

    warnings = "".join(f"<li>{text(error)}</li>" for error in errors)
    status = f'<section class="warning"><h2>수집 경로 오류 {len(errors)}건</h2><p>일부 경로를 수집하지 못했습니다. 아래 결과는 전체 자료를 대표하지 않을 수 있습니다.</p><ul>{warnings}</ul></section>' if errors else ""
    news = sum(item.get("source_type") == "news" for item in items)
    output = f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{text(args.keyword)} 맞춤 수집 보고서</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f5f4f5;color:#29262a;font-family:system-ui,sans-serif;line-height:1.7}}main{{max-width:1100px;margin:auto;padding:36px 20px}}h1{{color:#a50034;overflow-wrap:anywhere}}h2{{font-size:1.25rem}}header,section,article{{background:white;border:1px solid #ded9df;border-radius:6px;padding:24px;margin-bottom:18px}}.meta{{color:#68616b;font-size:.85rem}}.summary,.columns{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}.summary div{{background:#f9edf1;padding:16px;border-radius:4px}}.summary b{{display:block;color:#a50034;font-size:2rem}}.columns{{grid-template-columns:1fr 1fr}}ul{{padding:0;list-style:none}}li{{display:flex;justify-content:space-between;gap:16px;border-bottom:1px solid #eee;padding:8px 0}}a{{color:#a50034}}p,li{{overflow-wrap:anywhere}}.tags{{display:flex;flex-wrap:wrap;gap:6px}}.tags span{{background:#f9edf1;color:#85002a;padding:3px 8px;font-size:.8rem}}.warning{{border-color:#a50034}}.warning li{{display:block}}@media(max-width:600px){{.columns{{grid-template-columns:1fr}}main{{padding:20px 12px}}header,section,article{{padding:18px}}.summary{{gap:8px}}.summary div{{padding:10px}}}}@media print{{body{{background:white}}article{{break-inside:avoid}}}}
</style></head><body><main>
<header><p class="meta">OLED 맞춤 수집 보고서 · 독립 HTML 파일</p><h1>{text(args.keyword)}</h1><p>기간: {text(args.date_from or "2023-01-01")} ~ {text(args.date_to or "현재")} · 자료 유형: {source_label}</p><p class="meta">생성: {generated} (한국 시간) · 2023년 이전 자료 제외 · 최신 날짜순</p><p>공개 API·RSS가 제공한 제목과 요약을 정리했습니다. 원문 전체 분석 결과가 아니며, 이 보고서는 사이트 데이터에 추가되지 않습니다.</p><div class="summary"><div>전체<b>{len(items)}건</b></div><div>뉴스<b>{news}건</b></div><div>논문<b>{len(items)-news}건</b></div></div></header>
{status}<div class="columns"><section><h2>키워드별 자료 수</h2><ul>{counts(dict(keywords.most_common(15)))}</ul></section><section><h2>출처 현황</h2><ul>{counts(sources)}</ul></section></div>
<h2>수집 문서 {len(items)}건</h2>{"".join(cards) or "<section>검색 조건에 해당하는 자료가 없습니다.</section>"}
</main></body></html>'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(output, encoding="utf-8")
