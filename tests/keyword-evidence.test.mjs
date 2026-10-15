import test from "node:test";
import assert from "node:assert/strict";
import { buildKeywordEvidence } from "../src/lib/keywordEvidence.ts";

const make = (id, overrides = {}) => ({
  id, title: "OLED research", summary: "", url: `https://example.com/${id}`,
  source: "Test", published_at: "2026-01-01", keywords: ["LTPO"], ...overrides,
});

test("review counts exact keyword documents once and preserves evidence provenance", () => {
  const documents = [
    make("watch", { title: "Smartwatch OLED low power display", summary: "OLED fabrication and driving reliability are studied.", keywords: ["LTPO", "LTPO"], metrics: [{ name: "power", value: 200, unit: "mW", context: "OLED panel power consumption is 200 mW." }] }),
    make("phone", { title: "Smartphone OLED manufacturing process", metrics: [{ name: "yield", value: 90, unit: "%", context: "yield 90%" }] }),
    make("lab", { title: "Experimental OLED emitter" }),
    make("unknown", { title: "OLED research with no named application" }),
    make("unrelated", { title: "LTPO OLED in text only", keywords: ["LTPO variant"] }),
  ];
  const review = buildKeywordEvidence(documents, "ltpo");
  assert.equal(review.total, 4);
  assert.equal(review.criteria.length, 4);
  assert.deepEqual(review.criteria[0].sources.map((item) => item.id), ["watch"]);
  assert.deepEqual(review.criteria[1].sources.map((item) => item.id), ["watch"]);
  assert.match(review.criteria[1].sources[0].evidence, /200 mW/);
  assert.equal(review.criteria[1].sources[0].url, documents[0].url);
  assert.deepEqual(review.criteria[2].groups.map((group) => group.count), [1, 0, 1, 1, 1]);
  assert.equal(review.criteria[2].groups.reduce((sum, group) => sum + group.count, 0), review.total);
  assert.deepEqual(review.criteria[3].sources.map((item) => item.id), ["watch", "phone"]);
  assert.match(review.criteria[2].description, /실제 적용·성능 검증을 뜻하지 않습니다/);
});

test("missing evidence remains unconfirmed, not negative proof or an invented metric", () => {
  const review = buildKeywordEvidence([make("unknown", { metrics: [{ name: "power", value: 0, unit: "W", context: "" }] })], "LTPO");
  assert.equal(review.criteria[0].status, "원문 확인 필요");
  assert.equal(review.criteria[1].status, "원문 확인 필요");
  assert.equal(review.criteria[1].sources.length, 0);
  assert.equal(review.criteria[2].status, "적용 여부 원문 확인 필요");
  assert.equal(review.criteria[3].status, "원문 확인 필요");
  const empty = buildKeywordEvidence([], "LTPO");
  assert.equal(empty.total, 0);
  assert.ok(empty.criteria.every((criterion) => criterion.sources.length === 0));
});
