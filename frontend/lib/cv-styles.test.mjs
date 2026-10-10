import assert from "node:assert/strict";
import test from "node:test";
import { CV_STYLES, CV_TEMPLATES, detectedTemplate, pick, styleById, templateById, templatesByStyle } from "./cv-styles.js";

const LOCALES = ["az", "en", "ru"];

test("5 static styles are present and fully localised", () => {
  assert.deepEqual(CV_STYLES.map((s) => s.id), ["ats", "two_column", "photo", "academic", "creative"]);
  for (const s of CV_STYLES) {
    assert.ok(["good", "partial"].includes(s.reading));
    for (const loc of LOCALES) {
      assert.ok(pick(s.name, loc) && pick(s.desc, loc), `${s.id}/${loc}`);
      assert.ok(s.tips.length >= 2 && s.tips.every((tip) => pick(tip, loc)));
    }
  }
});

test("30 templates (15 worker-detected + 15 generic-only): unique ids, style, source, licence, text", () => {
  assert.equal(CV_TEMPLATES.length, 30);
  assert.equal(new Set(CV_TEMPLATES.map((t) => t.id)).size, 30);
  assert.equal(CV_TEMPLATES.filter((t) => t.worker).length, 15);
  for (const t of CV_TEMPLATES) {
    assert.ok(styleById(t.style), t.id);
    assert.ok(t.source.startsWith("github.com/") && t.license, t.id);
    assert.ok(["pdf", "docx"].includes(t.format));
    assert.ok(["good", "partial", "sample"].includes(t.reading));
    for (const loc of LOCALES) assert.ok(pick(t.desc, loc) && pick(t.tip, loc), `${t.id}/${loc}`);
  }
  assert.ok(CV_TEMPLATES.some((t) => t.format === "docx"));
});

test("every style has at least one template; lookups work", () => {
  for (const s of CV_STYLES) assert.ok(templatesByStyle(s.id).length >= 1, s.id);
  assert.equal(templateById("vantage_typst").name, "Typst Vantage");
  assert.equal(templateById("nope"), null);
});

test("template ids match the worker's template registry", async () => {
  const { readFileSync } = await import("node:fs");
  const src = readFileSync(new URL("../../worker/worker/cv_parse/templates.py", import.meta.url), "utf8");
  const workerIds = [...src.matchAll(/Template\(\s*"([a-z_]+)"/g)].map((m) => m[1]).sort();
  assert.deepEqual(workerIds, CV_TEMPLATES.filter((t) => t.worker).map((t) => t.id).sort());
});

test("pick falls back to English", () => {
  assert.equal(pick({ en: "x" }, "az"), "x");
  assert.equal(pick(null, "en"), "");
});

test("detectedTemplate: old profile, none, known, unknown id", () => {
  assert.equal(detectedTemplate({}), null);
  assert.equal(detectedTemplate(null), null);
  assert.equal(detectedTemplate({ template: { id: null } }).id, null);
  const known = detectedTemplate({ template: { id: "alta_typst", name: "Typst AltaCV", confidence: 1, applied: true } });
  assert.equal(known.entry.id, "alta_typst");
  assert.equal(known.style.id, "ats");
  assert.equal(known.applied, true);
  const unknown = detectedTemplate({ template: { id: "future_tpl", name: "Future" } });
  assert.equal(unknown.entry, null);
  assert.equal(unknown.name, "Future");
});

test("extra batch: sample-only files are listed as 'sample', real CVs have worker fixtures", async () => {
  const { existsSync } = await import("node:fs");
  const extra = CV_TEMPLATES.filter((t) => !t.worker);
  assert.equal(extra.length, 15);
  const samples = extra.filter((t) => t.reading === "sample").map((t) => t.id).sort();
  assert.deepEqual(samples, ["altacv_photo", "jakujobi", "jobhire_harvard", "moderncv_casual", "moderncv_es"]);
  for (const t of extra) {
    const fixture = new URL(`../../worker/tests/fixtures/cv_templates/${t.id}.txt`, import.meta.url);
    assert.equal(existsSync(fixture), t.reading !== "sample", t.id);
  }
});
