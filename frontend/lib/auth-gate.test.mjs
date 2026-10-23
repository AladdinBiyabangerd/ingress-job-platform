import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { copy } from "./copy.js";

const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");

const PAGES = [
  ["../components/my-applications.js", "applicationsGateTitle", "applicationsGate"],
  ["../components/my-saved.js", "savedJobsGateTitle", "savedJobsGate"],
  ["../components/email-settings.js", "emailSettingsGateTitle", "emailSettingsGate"],
  ["../components/profile-review.js", "profileReviewGateTitle", "profileGate"],
];

test("signed-out candidate pages use the shared centred AuthGate, not the old top-left mini card", () => {
  for (const [file, titleKey, textKey] of PAGES) {
    const src = read(file);
    assert.match(src, /import \{ AuthGate \} from "\.\/auth-gate";/, `${file} imports AuthGate`);
    assert.ok(src.includes(`title={t.${titleKey}}`), `${file} passes ${titleKey}`);
    assert.ok(src.includes(`message={t.${textKey}}`), `${file} passes ${textKey}`);
    assert.ok(!/-gate-actions/.test(src), `${file} has no legacy *-gate-actions markup`);
  }
});

test("AuthGate copy exists in az/en/ru", () => {
  for (const lang of ["az", "en", "ru"]) {
    for (const [, titleKey, textKey] of PAGES) {
      assert.ok(copy[lang][titleKey], `${lang}.${titleKey}`);
      assert.ok(copy[lang][textKey], `${lang}.${textKey}`);
    }
  }
  assert.equal(copy.az.applicationsGateTitle, "Müraciətlərini görmək üçün daxil ol");
});

test("AuthGate styles live in a CSS module and centre the card", () => {
  const css = read("../components/auth-gate.module.css");
  assert.match(css, /\.wrap \{[^}]*align-items: center;[^}]*justify-content: center;/s);
  const js = read("../components/auth-gate.js");
  assert.match(js, /import styles from "\.\/auth-gate\.module\.css";/);
});
