"""Public Crossref metadata collector. Python 3.10+, no third-party packages."""
import argparse
import hashlib
import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'wearable': 'wearable OLED display sunlight readability',
    'brightness': 'OLED high brightness luminous efficiency',
    'power': 'OLED low power LTPO display',
    'lifetime': 'OLED degradation lifetime tandem',
}
TAGS = {'야외 시인성': ('sunlight', 'ambient', 'reflectance', 'readability'),
        '밝기·효율': ('brightness', 'efficiency', 'luminance'),
        '전력·구동': ('power', 'ltpo', 'driving'),
        '수명·신뢰성': ('lifetime', 'degradation', 'aging'),
        '탠덤 OLED': ('tandem',), '웨어러블': ('wearable', 'watch')}

def normalize(item):
    title = ' '.join(item.get('title', []))
    if not title:
        return None
    searchable = title.lower()
    if not any(word in searchable for word in ('oled', 'organic light', 'organic electrolumines')):
        return None
    doi = item.get('DOI', '').lower().strip()
    url = 'https://doi.org/' + doi if doi else item.get('URL', '')
    if not url.startswith('https://'):
        return None
    parts = item.get('published', {}).get('date-parts', [[]])[0]
    date = '-'.join(str(p).zfill(2) for p in parts) if parts else '미공개'
    return {'id': doi or hashlib.sha256(url.encode()).hexdigest(), 'title': title,
            'url': url, 'published': date, 'source': 'Crossref', 'type': '논문 메타데이터',
            'publisher': item.get('publisher', '미공개'),
            'tags': [tag for tag, words in TAGS.items() if any(w in searchable for w in words)] or ['OLED'],
            'status': '자동 수집 · 미검토', 'measurement': '측정 수치·조건 미추출',
            'collected': datetime.now(timezone.utc).isoformat()}

def request_items(query, rows):
    endpoint = 'https://api.crossref.org/works?' + urlencode({
        'query': query, 'rows': rows, 'sort': 'published', 'order': 'desc',
        'filter': 'from-pub-date:2020-01-01',
        'select': 'DOI,title,URL,published,publisher,type'})
    for attempt in range(3):
        try:
            req = Request(endpoint, headers={'User-Agent': 'WearableOLEDObservatory/0.1 (local research MVP)'})
            with urlopen(req, timeout=30) as response:
                return json.load(response)['message']['items']
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)

def save_items(db, items):
    db.execute('CREATE TABLE IF NOT EXISTS articles (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
    added = 0
    for item in items:
        if item:
            added += db.execute('INSERT OR IGNORE INTO articles VALUES (?, ?)',
                                (item['id'], json.dumps(item, ensure_ascii=False))).rowcount
    db.commit()
    return added

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rows', type=int, default=30)
    parser.add_argument('--db', type=Path, default=ROOT / 'local-data/articles.sqlite')
    parser.add_argument('--output', type=Path, default=ROOT / 'src/data/articles.json')
    args = parser.parse_args()
    if not 1 <= args.rows <= 100:
        parser.error('--rows must be between 1 and 100')
    args.db.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    reports = []
    with sqlite3.connect(args.db) as db:
        save_items(db, [])
        for name, query in SOURCES.items():
            try:
                items = [normalize(item) for item in request_items(query, args.rows)]
                added = save_items(db, items)
                reports.append({'name': name, 'ok': True, 'accepted': sum(i is not None for i in items), 'added': added})
                logging.info('%s: %s accepted, %s added', name, reports[-1]['accepted'], added)
            except Exception as exc:
                logging.error('%s failed: %s', name, exc)
                reports.append({'name': name, 'ok': False, 'error': str(exc)})
            time.sleep(1)
        articles = [json.loads(row[0]) for row in db.execute('SELECT data FROM articles')]
    articles.sort(key=lambda item: item['published'], reverse=True)
    payload = {'updated': datetime.now(timezone.utc).isoformat(), 'reports': reports, 'articles': articles}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(args.output)
    if not any(report['ok'] for report in reports):
        raise SystemExit('All sources failed; existing articles were preserved.')
    logging.info('Exported %s articles to %s', len(articles), args.output)

if __name__ == '__main__':
    main()
