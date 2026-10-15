"""Generate clearly marked synthetic UI samples without altering the research DB."""
import json
from datetime import datetime, timezone
from collector.collect import ROOT

samples = [
    ('[데모] Wearable OLED sunlight readability', '2025-06-01', ['웨어러블', '야외 시인성']),
    ('[데모] High brightness tandem OLED efficiency', '2024-11-01', ['밝기·효율', '탠덤 OLED']),
    ('[데모] Low power OLED lifetime', '2023-02-01', ['전력·구동', '수명·신뢰성']),
]
articles = [{'id': f'demo-{index}', 'title': title, 'url': 'https://www.crossref.org/',
             'published': date, 'source': '합성 데모', 'type': '데모 · 실제 논문 아님',
             'publisher': 'UI 검증용 예시', 'tags': tags, 'status': '합성 자료 · 분석 사용 금지',
             'measurement': '실제 측정 자료 없음', 'collected': datetime.now(timezone.utc).isoformat()}
            for index, (title, date, tags) in enumerate(samples)]
output = ROOT / 'src/data/articles.json'
output.write_text(json.dumps({'demo': True, 'updated': None, 'reports': [], 'articles': articles}, ensure_ascii=False, indent=2), encoding='utf-8')
print('Wrote 3 synthetic UI samples. Research database unchanged. Run collect to replace the public export.')
