"""Render a standalone report without changing the dashboard's stored data."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.parse import urlsplit


REPORT_CONTROLS = """<script id="report-controls">
(() => {
  const list = document.querySelector('#report-documents');
  const select = document.querySelector('#report-sort');
  const resizeLists = () => {
    document.querySelectorAll('[data-visible-limit]').forEach(container => {
      const limit = Number(container.dataset.visibleLimit);
      const children = [...container.children];
      if (children.length <= limit) { container.style.maxHeight = 'none'; return; }
      const edge = children[limit - 1].getBoundingClientRect().bottom;
      const height = edge - container.getBoundingClientRect().top + container.scrollTop;
      container.style.maxHeight = `${height}px`;
    });
  };
  const sortDocuments = () => {
    const mode = select.value;
    const cards = [...list.querySelectorAll('article')];
    cards.sort((left, right) => {
      if (mode === 'source' || mode === 'title') {
        const compared = (left.dataset[mode] || '').localeCompare(right.dataset[mode] || '', 'ko');
        if (compared) return compared;
      }
      const a = left.dataset.date || '', b = right.dataset.date || '';
      const knownA = /^[0-9]{4}/.test(a), knownB = /^[0-9]{4}/.test(b);
      if (knownA !== knownB) return knownA ? -1 : 1;
      return (mode === 'oldest' ? 1 : -1) * a.localeCompare(b);
    });
    list.append(...cards);
    list.scrollTop = 0;
    resizeLists();
  };
  select.addEventListener('change', sortDocuments);
  window.addEventListener('resize', resizeLists);
  document.fonts.ready.then(resizeLists);
  sortDocuments();
})();
</script>"""


def write_report(path: Path, args, items: list[dict], errors: list[str]) -> None:
    def text(value):
        return escape(str(value or ""), quote=True)

    keywords = Counter(keyword for item in items for keyword in set(item.get("keywords", [])))
    sources = Counter(item.get("source", "출처 미상") for item in items)
    source_label = {"all": "뉴스 + 논문", "news": "뉴스", "papers": "논문"}[args.source]
    generated = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
    cards = []
    for item in items:
        url = item.get("url", "")
        safe_url = url if urlsplit(url).scheme.lower() in ("http", "https") else ""
        title = text(item.get("title"))
        link = f'<a href="{text(safe_url)}" target="_blank" rel="noopener noreferrer">{title}</a>' if safe_url else title
        kind = "뉴스" if item.get("source_type") == "news" else "논문"
        region = "국내" if item.get("region") == "domestic" else "해외"
        tags = "".join(f"<span>{text(keyword)}</span>" for keyword in item.get("keywords", []))
        cards.append(f'<article data-date="{text(item.get("published_at"))}" data-source="{text(item.get("source"))}" data-title="{text(item.get("title"))}"> <div class="meta">{kind} · {region} · {text(item.get("source"))} · {text(item.get("published_at") or "날짜 미상")}</div><h3>{link}</h3><p>{text(item.get("summary") or "제공된 요약이 없습니다. 원문 링크를 확인하세요.")}</p><div class="tags">{tags}</div></article>')
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
.columns section{{min-width:0}}.scroll-list{{overflow-y:auto;max-height:12rem;scrollbar-gutter:stable;margin-bottom:0}}.scroll-list b{{white-space:nowrap}}.scroll-documents{{overflow-y:auto;scrollbar-gutter:stable;max-height:100rem}}.scroll-documents article:last-child{{margin-bottom:0}}.document-toolbar{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px}}.document-toolbar label{{display:flex;align-items:center;gap:8px}}select{{font:inherit;padding:8px 12px;border:1px solid #b4abb6;background:white;color:#29262a;border-radius:4px}}:focus-visible{{outline:2px solid #a50034;outline-offset:3px}}@media print{{.scroll-list,.scroll-documents{{max-height:none!important;overflow:visible!important}}.document-toolbar label{{display:none}}}}
</style></head><body><main>
<header><p class="meta">OLED 맞춤 수집 보고서 · 독립 HTML 파일</p><h1>{text(args.keyword)}</h1><p>기간: {text(args.date_from or "2023-01-01")} ~ {text(args.date_to or "현재")} · 자료 유형: {source_label}</p><p class="meta">생성: {generated} (한국 시간) · 2023년 이전 자료 제외 · 최신 날짜순</p><p>공개 API·RSS가 제공한 제목과 요약을 정리했습니다. 원문 전체 분석 결과가 아니며, 이 보고서는 사이트 데이터에 추가되지 않습니다.</p><div class="summary"><div>전체<b>{len(items)}건</b></div><div>뉴스<b>{news}건</b></div><div>논문<b>{len(items)-news}건</b></div></div></header>
{status}<div class="columns"><section><h2>키워드별 자료 수</h2><ul class="scroll-list" data-visible-limit="4" tabindex="0" aria-label="키워드별 자료 수">{counts(keywords)}</ul></section><section><h2>출처 현황</h2><ul class="scroll-list" data-visible-limit="4" tabindex="0" aria-label="출처 현황">{counts(sources)}</ul></section></div>
<div class="document-toolbar"><h2>수집 문서 {len(items)}건</h2><label>정렬 <select id="report-sort" aria-label="수집 문서 정렬"><option value="newest">최신순</option><option value="oldest">오래된순</option><option value="source">출처순</option><option value="title">제목순</option></select></label></div>
<p class="meta">문서는 최대 5건까지 보입니다. 목록 안에서 스크롤해 나머지 문서를 확인하세요.</p>
<div id="report-documents" class="scroll-documents" data-visible-limit="5" tabindex="0" role="region" aria-label="수집 문서 목록">{"".join(cards) or "<section>검색 조건에 해당하는 자료가 없습니다.</section>"}</div>
</main>{REPORT_CONTROLS}</body></html>'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(output, encoding="utf-8")
