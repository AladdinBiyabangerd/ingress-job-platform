import assert from "node:assert/strict";
import test from "node:test";
import { cvChecks, cvFeedback, issueTarget } from "./cv-quality.js";

test("cvChecks flags empty profile", () => {
  assert.equal(cvChecks({}).every((c) => !c.ok), true);
});

test("cvChecks passes a complete profile", () => {
  const out = cvChecks({
    fullName: "A B", email: "a@b.co", phone: "1", headline: "Dev",
    work: [{ start: "2020-01" }], education: [{}], skills: [1, 2, 3], languages: [{}],
  });
  assert.equal(out.every((c) => c.ok), true);
});

test("cvChecks: undated job fails work", () => {
  assert.equal(cvChecks({ work: [{ start: "2020-01" }, { start: "" }] }).find((c) => c.id === "work").ok, false);
});

test("cvFeedback: null without quality data", () => {
  assert.equal(cvFeedback({}), null);
  assert.equal(cvFeedback(null), null);
});

test("cvFeedback: rules-only good parse", () => {
  const f = cvFeedback({ parse_source: "rules", quality: { score: 0.9, threshold: 0.65, issues: [] } });
  assert.equal(f.level, "ok");
  assert.equal(f.source, "rules");
  assert.equal(f.ai, "none");
});

test("cvFeedback: ai repaired, unknown issues dropped", () => {
  const f = cvFeedback({
    parse_source: "mixed", ai_fallback: "applied",
    quality: { score: 0.7, score_before: 0.3, threshold: 0.65, issues: ["work_undated", "evil<script>"] },
  });
  assert.equal(f.source, "mixed");
  assert.equal(f.ai, "applied");
  assert.equal(f.before, 0.3);
  assert.deepEqual(f.issues, ["work_undated"]);
  assert.equal(f.level, "partial");
});

test("cvFeedback: ai failed keeps low level", () => {
  const f = cvFeedback({ parse_source: "rules", ai_fallback: "failed", quality: { score: 0.3, threshold: 0.65, issues: ["work_missing"] } });
  assert.equal(f.ai, "failed");
  assert.equal(f.level, "low");
});

test("issueTarget maps issues to sections", () => {
  assert.equal(issueTarget("work_undated"), "work");
  assert.equal(issueTarget("education_missing"), "education");
  assert.equal(issueTarget("name_missing"), "name");
});

test("cvFeedback: AI skipped for unreadable text is flagged", () => {
  const f = cvFeedback({
    ai_fallback: "skipped", ai_error: "text_too_short",
    quality: { score: 0.2, threshold: 0.65, issues: ["text_too_short"] },
  });
  assert.equal(f.aiSkippedUnreadable, true);
  const g = cvFeedback({ ai_fallback: "skipped", ai_error: "ai_disabled", quality: { score: 0.2, issues: ["text_garbled"] } });
  assert.equal(g.aiSkippedUnreadable, false);
  assert.deepEqual(g.issues, ["text_garbled"]);
});
