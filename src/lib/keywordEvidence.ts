export type EvidenceDocument = {
  id: string;
  title: string;
  summary: string;
  url: string;
  source: string;
  published_at: string;
  keywords?: string[];
  metrics?: { name: string; value: number; unit: string; context: string }[];
};

const topicRules = [
  { label: "휘도", pattern: /brightness|luminance|\bnits?\b|휘도|밝기/i },
  { label: "전력 효율", pattern: /power (?:consumption|efficiency)|energy efficiency|low[- ]power|battery|소비전력|전력 효율|저전력|배터리/i },
  { label: "야외 시인성", pattern: /sunlight|outdoor|reflectance|reflection|polarizer|야외|외광|반사율|저반사|무편광판/i },
];
const developmentRules = [
  { label: "공정·제조", pattern: /fabricat|manufactur|process|encapsulat|yield|공정|제조|봉지|수율/i },
  { label: "구동·신뢰성", pattern: /driv(?:ing|er)|reliability|lifetime|stability|degradation|구동|신뢰성|수명|열화|안정성/i },
  { label: "양산·제품 관련 표현", pattern: /mass produc|commercial|prototype|product|양산|상용|시제품|출시|제품/i },
];
const targetRules = [
  { label: "스마트워치 언급", pattern: /smart\s*watch|watch display|스마트\s*워치|워치용/i },
  { label: "웨어러블 언급", pattern: /wearable|웨어러블/i },
  { label: "타 기기 언급", pattern: /\bTV\b|television|smartphone|laptop|notebook|tablet|monitor|vehicle|스마트폰|노트북|태블릿|모니터|차량/i },
  { label: "실험 소자 언급", pattern: /experimental|laboratory|diode|emitter|실험|소자|발광체/i },
];
const metricLabels: Record<string, string> = { brightness: "휘도", reflectance: "반사율", power: "소비전력", lifetime: "OLED 수명" };

function content(item: EvidenceDocument) {
  return `${item.title}\n${item.summary}`;
}

function source(item: EvidenceDocument, evidence: string) {
  return { id: item.id, title: item.title, url: item.url, source: item.source, date: item.published_at, evidence };
}

function matchingSentence(item: EvidenceDocument, pattern: RegExp) {
  return content(item).split(/\n|(?<=[.!?。！？])\s+/).filter((sentence) => pattern.test(sentence)).join(" ");
}

export function buildKeywordEvidence(documents: EvidenceDocument[], keyword: string) {
  const matching = documents.filter((item) => item.keywords?.some((term) => term.trim().toLowerCase() === keyword.trim().toLowerCase()));
  const topicPattern = new RegExp(topicRules.map((rule) => rule.pattern.source).join("|"), "i");
  const developmentPattern = new RegExp(developmentRules.map((rule) => rule.pattern.source).join("|"), "i");
  const topicDocuments = matching.filter((item) => topicPattern.test(content(item)));
  const metricDocuments = matching.flatMap((item) => {
    const metrics = (item.metrics || []).filter((metric) => metricLabels[metric.name] && Number.isFinite(metric.value) && metric.value > 0);
    return metrics.length ? [source(item, metrics.map((metric) => `${metricLabels[metric.name]} ${metric.value.toLocaleString("ko-KR")} ${metric.unit} — ${metric.context}`).join("\n"))] : [];
  });
  const targets = matching.map((item) => ({ item, label: targetRules.find((rule) => rule.pattern.test(content(item)))?.label || "대상 확인 필요" }));
  const developmentDocuments = matching.filter((item) => developmentPattern.test(content(item)));
  return {
    keyword,
    total: matching.length,
    criteria: [
      {
        title: "주제와의 직접 관련성",
        status: topicDocuments.length ? "관련 표현 확인" : "원문 확인 필요",
        description: "휘도·전력 효율·야외 시인성 표현을 찾은 자료입니다. 주제별 건수는 서로 겹칠 수 있습니다.",
        groups: topicRules.map((rule) => ({ label: rule.label, count: matching.filter((item) => rule.pattern.test(content(item))).length })),
        sources: topicDocuments.map((item) => source(item, matchingSentence(item, topicPattern))),
      },
      {
        title: "공개 성능 근거 유무",
        status: metricDocuments.length ? "추출 수치 있음" : "원문 확인 필요",
        description: "휘도·반사율·소비전력·OLED 수명 수치가 추출된 자료입니다. 수치가 있어도 성능과 측정 조건이 검증된 것은 아닙니다.",
        groups: [{ label: "수치가 있는 자료", count: metricDocuments.length }, { label: "요약에서 수치 미확인", count: matching.length - metricDocuments.length }],
        sources: metricDocuments,
      },
      {
        title: "스마트워치 적용 근거",
        status: targets.some((entry) => entry.label === "스마트워치 언급") ? "스마트워치 언급 있음" : "적용 여부 원문 확인 필요",
        description: "제목·요약의 표현으로 나눈 자료 현황입니다. 스마트워치 언급이 실제 적용·성능 검증을 뜻하지 않습니다. 각 자료는 아래 순서로 한 번만 분류합니다.",
        groups: [...targetRules.map((rule) => rule.label), "대상 확인 필요"].map((label) => ({ label, count: targets.filter((entry) => entry.label === label).length })),
        sources: targets.map(({ item, label }) => {
          const rule = targetRules.find((entry) => entry.label === label);
          return source(item, `${label}: ${rule ? matchingSentence(item, rule.pattern) : "제목·요약에서 적용 대상을 확인하지 못했습니다."}`);
        }),
      },
      {
        title: "제조·개발 검토 가능성",
        status: developmentDocuments.length ? "관련 표현 확인" : "원문 확인 필요",
        description: "공정·구동·신뢰성·양산 관련 표현이 있는 자료입니다. 제조 난이도나 상용화 단계를 판정한 결과는 아닙니다. 항목별 건수는 겹칠 수 있습니다.",
        groups: developmentRules.map((rule) => ({ label: rule.label, count: matching.filter((item) => rule.pattern.test(content(item))).length })),
        sources: developmentDocuments.map((item) => source(item, matchingSentence(item, developmentPattern))),
      },
    ],
  };
}
