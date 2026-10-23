import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { thresholdMatchIds } from "./admin-threshold.js";
import { copy } from "./copy.js";

const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");

const ITEMS = [
  { id: 1, status: "pending", ai_confidence: 20, rule_confidence: 90 },
  { id: 2, status: "pending", ai_confidence: 40, rule_confidence: 10 },
  { id: 3, status: "pending", ai_confidence: 80, rule_confidence: "" },
  { id: 4, status: "pending", ai_confidence: null, rule_confidence: 50 },
  { id: 5, status: "rejected", ai_confidence: 10, rule_confidence: 10 },
  { id: 6, status: "published", ai_confidence: 5, rule_confidence: 5 },
];

test("threshold match: AI ≤ / ≥ with inclusive edge, unscored never matches", () => {
  assert.deepEqual(thresholdMatchIds(ITEMS, "ai", "lte", 40), [1, 2]);
  assert.deepEqual(thresholdMatchIds(ITEMS, "ai", "gte", 40), [2, 3]);
  assert.deepEqual(thresholdMatchIds(ITEMS, "ai", "gte", "99"), []);
});

test("AI re-check: «≤ N» also takes unscored rows, «≥ N» and publish/reject do not", () => {
  const opts = { includeUnscored: true };
  assert.deepEqual(thresholdMatchIds(ITEMS, "ai", "lte", 0, "pending", opts), [4]);
  assert.deepEqual(thresholdMatchIds(ITEMS, "ai", "lte", 40, "pending", opts), [1, 2, 4]);
  assert.deepEqual(thresholdMatchIds(ITEMS, "ai", "gte", 40, "pending", opts), [2, 3]);
  assert.deepEqual(thresholdMatchIds(ITEMS, "ai", "lte", 0), []);
});

test("threshold match: rule score and rejected status are separate", () => {
  assert.deepEqual(thresholdMatchIds(ITEMS, "rule", "gte", 50), [1, 4]);
  assert.deepEqual(thresholdMatchIds(ITEMS, "rule", "lte", 50, "rejected"), [5]);
  assert.deepEqual(thresholdMatchIds(ITEMS, "ai", "lte", ""), []);
});

test("queue threshold panel has only publish / AI re-check / reject, no limit or extras", () => {
  const src = read("../components/admin.js");
  const start = src.indexOf('<div className="admin-mod-threshold">');
  const end = src.indexOf('{tab === "queue" && selectedCount ? (', start);
  assert.ok(start > 0 && end > start);
  const panel = src.slice(start, end);
  const buttons = panel.match(/<button\b/g) || [];
  assert.equal(buttons.length, 3);
  for (const key of ["adminThresholdPublish}", "adminThresholdRecheck}", "adminThresholdReject}"]) {
    assert.ok(panel.includes(`{t.${key}`), key);
  }
  assert.ok(!panel.includes("adminThresholdPublishQuick"));
  assert.ok(!panel.includes("recheckLimit"));
  assert.ok(!panel.includes("backfillConfidence"));
  assert.ok(!src.includes("RECHECK_FRESH_MAX"));
});

test("threshold panel copy exists in az/en/ru", () => {
  for (const locale of ["az", "en", "ru"]) {
    const t = copy[locale];
    assert.equal(typeof t.adminThresholdReject, "string", locale);
    assert.equal(typeof t.adminThresholdRejectTitle, "string", locale);
    assert.match(t.adminThresholdRejectConfirm(7), /7/);
    assert.match(t.adminThresholdRejectedNote(3), /3/);
    assert.match(t.adminThresholdRejectReason("AI", "≤", 40), /AI ≤ 40%/);
    assert.match(t.adminRecheckConfirmThreshold(12), /12/);
    assert.match(t.adminRecheckQueued(12), /12/);
    assert.match(t.adminRecheckBudgetHalt(5), /5/);
    assert.equal(t.adminRecheckLimit, undefined);
    assert.equal(t.adminBackfillConfidence, undefined);
  }
  assert.equal(copy.az.adminThresholdReject, "Faizə uyğun rədd et");
  assert.equal(copy.az.adminThresholdPublish, "Faizə görə dərc et");
  assert.equal(copy.az.adminThresholdRecheck, "AI ilə yenidən yoxla");
});
