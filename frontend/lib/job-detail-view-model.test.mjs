import assert from "node:assert/strict";
import test from "node:test";
import { descriptionBlocks } from "./description.js";
import { benefitsFromSections, sectionsFromBlocks } from "./job-detail-sections.js";

test("maps Relocue-style headings into known section ids", () => {
  const raw = [
    "Why this role is interesting:",
    "• Shape a travel technology product with global reach.",
    "• Own backend delivery and influence product direction.",
    "",
    "What you'll do:",
    "• Deliver documented Python services and APIs.",
    "",
    "What Distribusion is looking for:",
    "• Python backend lifecycle ownership.",
    "",
    "Preferred qualifications and technologies:",
    "• FastAPI, Django and ReactJS.",
    "",
    "Nice to have:",
    "• Docker and Kubernetes.",
    "",
    "What the employer offers:",
    "• Flexible work",
    "• Growth opportunities",
  ].join("\n");

  const sections = sectionsFromBlocks(descriptionBlocks(raw));
  const byId = Object.fromEntries(sections.map((s) => [s.id, s]));
  assert.equal(byId.why?.type, "list");
  assert.equal(byId.responsibilities?.type, "list");
  assert.equal(byId.requirements?.type, "list");
  assert.equal(byId.nice?.type, "list");
  assert.equal(byId.benefits?.type, "list");
  assert.ok(byId.requirements.items.some((item) => /Python backend/i.test(item)));
  assert.ok(byId.nice.items.some((item) => /FastAPI|Django/i.test(item)));
  assert.equal(benefitsFromSections(sections).length, 2);
});
